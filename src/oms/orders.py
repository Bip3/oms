from typing import Any, Dict, Optional, List, Tuple

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
    normalized: List[tuple[int, int]] = []
    for it in items:
        pid = int(it["product_id"])
        qty = int(it["quantity"])
        if qty <= 0:
            raise ValueError("Order number can not be negative")
        normalized.append((pid, qty))
    product_ids = [pid for pid, _ in normalized]

    try:
        with conn.cursor() as cur:
            #Checking that customer exists
            cur.execute("SELECT id FROM customers WHERE id = %s", (customer_id,))
            if not cur.fetchone():
                raise ValueError("Customer not found")
            
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
                    raise KeyError(f"Product not found:{pid}")
                if not by_id[pid]["is_active"]:
                    raise ValueError(f"Product inactive:{pid}")
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


