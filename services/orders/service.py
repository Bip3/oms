from typing import Any, Dict, List, Optional

from .helpers import (
    apply_stock_delta,
    compute_total,
    ensure_products_active,
    ensure_products_exist,
    ensure_stock_available,
    fetch_order_items,
    fetch_products_for_update,
    normalize_items,
)

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
        super().__init__(
            f"Product {product_id} out of stock (available={available}, requested={requested})"
        )


def create_order(conn, customer_id: int, items: List[Dict[str, int]]) -> Dict[str, Any]:
    normalized = normalize_items(items)
    product_ids = [pid for pid, _ in normalized]

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM customers WHERE id = %s", (customer_id,))
            if not cur.fetchone():
                raise KeyError("CUSTOMER_NOT_FOUND")

            by_id = fetch_products_for_update(conn, product_ids)
            ensure_products_exist(by_id, product_ids)
            ensure_products_active(by_id, product_ids)
            ensure_stock_available(by_id, normalized, OutOfStockError)

            cur.execute(
                """
                INSERT INTO orders (customer_id, status, total_cents)
                VALUES (%s, 'PENDING', 0)
                RETURNING id, customer_id, status, total_cents, created_at, updated_at
                """,
                (customer_id,),
            )
            order = cur.fetchone()
            order_id = order["id"]

            total = 0
            stock_deltas: List[tuple[int, int]] = []
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
                stock_deltas.append((pid, qty))

            apply_stock_delta(conn, stock_deltas)
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
    order["items"] = fetch_order_items(conn, order_id)
    return order


def update_order_items(conn, order_id: int, items: List[Dict[str, int]]) -> Dict[str, Any]:
    normalized = normalize_items(items)
    new_qty_by_id = {pid: qty for pid, qty in normalized}
    product_ids = list(new_qty_by_id.keys())

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
            order_row = cur.fetchone()
            if not order_row:
                raise KeyError("ORDER_NOT_FOUND")
            if order_row["status"] != "PENDING":
                raise ValueError("ORDER_NOT_PENDING")

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

            all_product_ids = list({*product_ids, *old_qty_by_id.keys()})
            by_id = fetch_products_for_update(conn, all_product_ids)
            ensure_products_exist(by_id, all_product_ids)
            ensure_products_active(by_id, product_ids)
            deltas = [
                (pid, new_qty_by_id.get(pid, 0) - old_qty_by_id.get(pid, 0))
                for pid in all_product_ids
            ]
            ensure_stock_available(by_id, deltas, OutOfStockError)

            apply_stock_delta(conn, deltas)

            for pid in all_product_ids:
                old_qty = old_qty_by_id.get(pid, 0)
                new_qty = new_qty_by_id.get(pid, 0)
                delta = new_qty - old_qty

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

            items_out = fetch_order_items(conn, order_id)
            total = compute_total(items_out)

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
                order["items"] = fetch_order_items(conn, order_id)
                return order

            if new_status not in ALLOWED_STATUS_TRANSITIONS[current]:
                raise ValueError("INVALID_STATUS_TRANSITION")

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
                    fetch_products_for_update(conn, product_ids)
                    apply_stock_delta(
                        conn, [(r["product_id"], -r["quantity"]) for r in items]
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
            order["items"] = fetch_order_items(conn, order_id)

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
                fetch_products_for_update(conn, product_ids)
                apply_stock_delta(
                    conn, [(r["product_id"], -r["quantity"]) for r in items]
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
