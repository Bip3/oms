from typing import Any, Dict, Optional, List, Tuple

ALLOWED_STATUS_TRANSITIONS = {
    "PENDING": {"CONFIRMED", "CANCELLED"},
    "CONFIRMED": {"SHIPPED", "CANCELLED"},
    "SHIPPED": {"DELIVERED"},
    "DELIVERED": set(),
    "CANCELLED": set(),
}

class OutOfStockError(Exception):
    def __init__(self, product_id: int, available: int, requested: int):
        self.product_id = product_id
        self.available = available
        self.requested = requested
        super().__init__(f"Product {product_id} out of stock (available={available}, requested={requested})")
    
def create_order(conn, customer_id: int, items: List[Dict[str,int]]) -> Dict[str, Any]:
    """
    items: [{ "product_id": int, "quantity": int}, ...]
    Inventory-safe: locks product row FOR UPDATE, checks stock, decrements stock, inserts order and items.
    """
    if not items:
        raise ValueError("Order must have at least one item")
    
    #Normalization and validation of quantities
    qty_by_id: Dict[int, int] = {}
    for it in items:
        pid = int(it["product_id"])
        qty = int(it["quantity"])
        if qty <= 0:
            raise ValueError("Order quantity must be positive")
        qty_by_id[pid] = qty_by_id.get(pid, 0) + qty
    normalized = list(qty_by_id.items())
    product_ids = [pid for pid, _ in normalized]

    try:
        with conn.cursor() as cur:
            #Checking that customer exists
            cur.execute("SELECT id FROM customers WHERE id = %s", (customer_id,))
            if not cur.fetchone():
                raise KeyError("CUSTOMER_NOT_FOUND")
            
            #Lock products for this order
            cur.execute(
                """
                SELECT id, price_cents, stock_quantity, is_active
                FROM products
                WHERE id = ANY(%s)
                FOR UPDATE
                """,
                (product_ids, ),
            )
            rows = cur.fetchall() or []
            by_id = {r["id"]: r for r in rows}

            #Validating all products are present, active, and have enough stock
            for pid, qty in normalized:
                if pid not in by_id:
                    raise KeyError(f"PRODUCT_NOT_FOUND:{pid}")
                if not by_id[pid]["is_active"]:
                    raise ValueError(f"PRODUCT_INACTIVE:{pid}")
                available = by_id[pid]["stock_quantity"]
                if available < qty:
                    raise OutOfStockError(pid, available, qty)
            #Create order
            cur.execute(
                """
                INSERT INTO orders (customer_id, status, total_cents)
                VALUES (%s, 'PENDING', 0)
                RETURNING id, customer_id, status, total_cents, created_at, updated_at
                """,
                (customer_id, ),
            )
            order = cur.fetchone()
            order_id = order["id"]

            #Insert items and decrement stock
            total = 0
            created_items: List[Dict[str, Any]] = []
            for pid, qty in normalized:
                unit = by_id[pid]["price_cents"]
                line_total = unit * qty
                total += line_total

                cur.execute(
                    """
                    INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents, line_total_cents)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING product_id, quantity, unit_price_cents, line_total_cents
                    """,
                    (order_id, pid, qty, unit, line_total),
                )
                created_items.append(cur.fetchone())

                cur.execute(
                    """
                    UPDATE products
                    SET stock_quantity = stock_quantity - %s, updated_at = now()
                    WHERE id = %s
                    """,
                    (qty, pid),
                )
            #update order total
            cur.execute(
                """
                UPDATE orders
                SET total_cents = %s, updated_at = now()
                WHERE id = %s
                RETURNING id, customer_id, status, total_cents, created_at, updated_at
                """,
                (total, order_id),
            )
            order = cur.fetchone()
            order["items"] = created_items
        
        conn.commit()
        return order
    except Exception:
        conn.rollback()
        raise

def get_order_by_id(conn, order_id: int) -> Optional[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, customer_id, status, total_cents, created_at, updated_at
            FROM orders
            WHERE id = %s
            """,
            (order_id,),
        )
        order = cur.fetchone()
        if not order:
            return None
        cur.execute(
            """
            SELECT product_id, quantity, unit_price_cents, line_total_cents
            FROM order_items
            WHERE order_id = %s
            ORDER BY product_id
            """,
            (order_id,),
        )
        order["items"] = cur.fetchall() or []
        return order

def update_order_items(conn, order_id: int, items: List[Dict[str, int]]) -> Dict[str, Any]:
    """
    Replace order items for a PENDING order.
    Adjusts stock based on delta between old and new quantities.
    """
    if not items:
        raise ValueError("Order must have at least one item")

    qty_by_id: Dict[int, int] = {}
    for it in items:
        pid = int(it["product_id"])
        qty = int(it["quantity"])
        if qty <= 0:
            raise ValueError("Order quantity must be positive")
        qty_by_id[pid] = qty_by_id.get(pid, 0) + qty

    new_qty_by_id = qty_by_id
    product_ids = list(new_qty_by_id.keys())

    try:
        with conn.cursor() as cur:
            # Lock order row
            cur.execute(
                """
                SELECT id, status
                FROM orders
                WHERE id = %s
                FOR UPDATE
                """,
                (order_id,),
            )
            order_row = cur.fetchone()
            if not order_row:
                raise KeyError("ORDER_NOT_FOUND")
            if order_row["status"] != "PENDING":
                raise ValueError("ORDER_NOT_PENDING")

            # Fetch existing items
            cur.execute(
                """
                SELECT product_id, quantity, unit_price_cents
                FROM order_items
                WHERE order_id = %s
                """,
                (order_id,),
            )
            existing_items = cur.fetchall() or []
            old_qty_by_id = {r["product_id"]: r["quantity"] for r in existing_items}
            old_unit_by_id = {r["product_id"]: r["unit_price_cents"] for r in existing_items}

            # Lock all involved products
            all_product_ids = list({*product_ids, *old_qty_by_id.keys()})
            cur.execute(
                """
                SELECT id, price_cents, stock_quantity, is_active
                FROM products
                WHERE id = ANY(%s)
                FOR UPDATE
                """,
                (all_product_ids,),
            )
            rows = cur.fetchall() or []
            by_id = {r["id"]: r for r in rows}

            # Validate products
            for pid in all_product_ids:
                if pid not in by_id:
                    raise KeyError(f"PRODUCT_NOT_FOUND:{pid}")
            for pid in product_ids:
                if not by_id[pid]["is_active"]:
                    raise ValueError(f"PRODUCT_INACTIVE:{pid}")

            # Check stock for increases
            for pid in all_product_ids:
                old_qty = old_qty_by_id.get(pid, 0)
                new_qty = new_qty_by_id.get(pid, 0)
                delta = new_qty - old_qty
                if delta > 0:
                    available = by_id[pid]["stock_quantity"]
                    if available < delta:
                        raise OutOfStockError(pid, available, delta)

            # Apply item changes and stock updates
            for pid in all_product_ids:
                old_qty = old_qty_by_id.get(pid, 0)
                new_qty = new_qty_by_id.get(pid, 0)
                delta = new_qty - old_qty

                if delta != 0:
                    cur.execute(
                        """
                        UPDATE products
                        SET stock_quantity = stock_quantity - %s, updated_at = now()
                        WHERE id = %s
                        """,
                        (delta, pid),
                    )

                if old_qty == 0 and new_qty > 0:
                    unit = by_id[pid]["price_cents"]
                    line_total = unit * new_qty
                    cur.execute(
                        """
                        INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents, line_total_cents)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING product_id, quantity, unit_price_cents, line_total_cents
                        """,
                        (order_id, pid, new_qty, unit, line_total),
                    )
                    cur.fetchone()
                elif old_qty > 0 and new_qty == 0:
                    cur.execute(
                        """
                        DELETE FROM order_items
                        WHERE order_id = %s AND product_id = %s
                        """,
                        (order_id, pid),
                    )
                elif old_qty > 0 and new_qty > 0:
                    unit = old_unit_by_id[pid]
                    line_total = unit * new_qty
                    cur.execute(
                        """
                        UPDATE order_items
                        SET quantity = %s, line_total_cents = %s
                        WHERE order_id = %s AND product_id = %s
                        RETURNING product_id, quantity, unit_price_cents, line_total_cents
                        """,
                        (new_qty, line_total, order_id, pid),
                    )
                    cur.fetchone()

            # Fetch updated items and compute total
            cur.execute(
                """
                SELECT product_id, quantity, unit_price_cents, line_total_cents
                FROM order_items
                WHERE order_id = %s
                ORDER BY product_id
                """,
                (order_id,),
            )
            items_out = cur.fetchall() or []
            total = sum(i["line_total_cents"] for i in items_out)

            # Update order total
            cur.execute(
                """
                UPDATE orders
                SET total_cents = %s, updated_at = now()
                WHERE id = %s
                RETURNING id, customer_id, status, total_cents, created_at, updated_at
                """,
                (total, order_id),
            )
            order = cur.fetchone()
            order["items"] = items_out

        conn.commit()
        return order
    except Exception:
        conn.rollback()
        raise

def update_order_status(conn, order_id: int, new_status: str) -> Dict[str, Any]:
    new_status = new_status.upper()
    if new_status not in ALLOWED_STATUS_TRANSITIONS:
        raise ValueError("INVALID_STATUS")

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, status, customer_id, total_cents, created_at, updated_at
                FROM orders
                WHERE id = %s
                FOR UPDATE
                """,
                (order_id,),
            )
            order = cur.fetchone()
            if not order:
                raise KeyError("ORDER_NOT_FOUND")

            current = order["status"]
            if current == new_status:
                cur.execute(
                    """
                    SELECT product_id, quantity, unit_price_cents, line_total_cents
                    FROM order_items
                    WHERE order_id = %s
                    ORDER BY product_id
                    """,
                    (order_id,),
                )
                order["items"] = cur.fetchall() or []
                return order

            if new_status not in ALLOWED_STATUS_TRANSITIONS[current]:
                raise ValueError("INVALID_STATUS_TRANSITION")

            # Restock on cancel if not shipped
            if new_status == "CANCELLED" and current in {"PENDING", "CONFIRMED"}:
                cur.execute(
                    """
                    SELECT product_id, quantity
                    FROM order_items
                    WHERE order_id = %s
                    """,
                    (order_id,),
                )
                items = cur.fetchall() or []
                product_ids = [r["product_id"] for r in items]
                if product_ids:
                    cur.execute(
                        """
                        SELECT id
                        FROM products
                        WHERE id = ANY(%s)
                        FOR UPDATE
                        """,
                        (product_ids,),
                    )
                    for r in items:
                        cur.execute(
                            """
                            UPDATE products
                            SET stock_quantity = stock_quantity + %s, updated_at = now()
                            WHERE id = %s
                            """,
                            (r["quantity"], r["product_id"]),
                        )

            cur.execute(
                """
                UPDATE orders
                SET status = %s, updated_at = now()
                WHERE id = %s
                RETURNING id, customer_id, status, total_cents, created_at, updated_at
                """,
                (new_status, order_id),
            )
            order = cur.fetchone()
            cur.execute(
                """
                SELECT product_id, quantity, unit_price_cents, line_total_cents
                FROM order_items
                WHERE order_id = %s
                ORDER BY product_id
                """,
                (order_id,),
            )
            order["items"] = cur.fetchall() or []

        conn.commit()
        return order
    except Exception:
        conn.rollback()
        raise

def delete_order(conn, order_id: int) -> bool:
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, status
                FROM orders
                WHERE id = %s
                FOR UPDATE
                """,
                (order_id,),
            )
            order = cur.fetchone()
            if not order:
                return False
            if order["status"] != "PENDING":
                raise ValueError("ORDER_NOT_PENDING")

            cur.execute(
                """
                SELECT product_id, quantity
                FROM order_items
                WHERE order_id = %s
                """,
                (order_id,),
            )
            items = cur.fetchall() or []
            product_ids = [r["product_id"] for r in items]
            if product_ids:
                cur.execute(
                    """
                    SELECT id
                    FROM products
                    WHERE id = ANY(%s)
                    FOR UPDATE
                    """,
                    (product_ids,),
                )
                for r in items:
                    cur.execute(
                        """
                        UPDATE products
                        SET stock_quantity = stock_quantity + %s, updated_at = now()
                        WHERE id = %s
                        """,
                        (r["quantity"], r["product_id"]),
                    )

            cur.execute(
                """
                DELETE FROM orders
                WHERE id = %s
                """,
                (order_id,),
            )
            deleted = cur.rowcount > 0

        conn.commit()
        return deleted
    except Exception:
        conn.rollback()
        raise

def list_orders_by_customer(conn, customer_id: int) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, customer_id, status, total_cents, created_at, updated_at
            FROM orders
            WHERE customer_id = %s
            ORDER BY created_at DESC
            """,
            (customer_id,),
        )
        return cur.fetchall() or []

def list_orders_by_date_range(conn, start_dt, end_dt) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, customer_id, status, total_cents, created_at, updated_at
            FROM orders
            WHERE created_at >= %s AND created_at <= %s
            ORDER BY created_at DESC
            """,
            (start_dt, end_dt),
        )
        return cur.fetchall() or []

def top_selling_products(conn, start_dt, end_dt, limit: int) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                p.id AS product_id,
                p.sku,
                p.name,
                SUM(oi.quantity) AS total_quantity,
                SUM(oi.line_total_cents) AS total_sales_cents
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            JOIN products p ON p.id = oi.product_id
            WHERE o.created_at >= %s
              AND o.created_at <= %s
              AND o.status != 'CANCELLED'
            GROUP BY p.id, p.sku, p.name
            ORDER BY total_quantity DESC
            LIMIT %s
            """,
            (start_dt, end_dt, limit),
        )
        return cur.fetchall() or []


