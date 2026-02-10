from typing import Any, Dict, Iterable, List, Tuple


def normalize_items(items: List[Dict[str, int]]) -> List[Tuple[int, int]]:
    if not items:
        raise ValueError("Order must have at least one item")

    qty_by_id: Dict[int, int] = {}
    for it in items:
        pid = int(it["product_id"])
        qty = int(it["quantity"])
        if qty <= 0:
            raise ValueError("Order quantity must be positive")
        qty_by_id[pid] = qty_by_id.get(pid, 0) + qty
    return list(qty_by_id.items())


def fetch_products_for_update(conn, product_ids: Iterable[int]) -> Dict[int, Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, price_cents, stock_quantity, is_active
            FROM products
            WHERE id = ANY(%s)
            FOR UPDATE
            """,
            (list(product_ids),),
        )
        rows = cur.fetchall() or []
    return {r["id"]: r for r in rows}


def ensure_products_exist(by_id: Dict[int, Dict[str, Any]], product_ids: Iterable[int]) -> None:
    for pid in product_ids:
        if pid not in by_id:
            raise KeyError(f"PRODUCT_NOT_FOUND:{pid}")


def ensure_products_active(by_id: Dict[int, Dict[str, Any]], product_ids: Iterable[int]) -> None:
    for pid in product_ids:
        if not by_id[pid]["is_active"]:
            raise ValueError(f"PRODUCT_INACTIVE:{pid}")


def ensure_stock_available(
    by_id: Dict[int, Dict[str, Any]],
    deltas: Iterable[Tuple[int, int]],
    out_of_stock_error,
) -> None:
    for pid, delta in deltas:
        if delta <= 0:
            continue
        available = by_id[pid]["stock_quantity"]
        if available < delta:
            raise out_of_stock_error(pid, available, delta)


def apply_stock_delta(conn, deltas: Iterable[Tuple[int, int]]) -> None:
    with conn.cursor() as cur:
        for pid, delta in deltas:
            if delta == 0:
                continue
            cur.execute(
                """
                UPDATE products
                SET stock_quantity = stock_quantity - %s, updated_at = now()
                WHERE id = %s
                """,
                (delta, pid),
            )


def fetch_order_items(conn, order_id: int) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT product_id, quantity, unit_price_cents, line_total_cents
            FROM order_items
            WHERE order_id = %s
            ORDER BY product_id
            """,
            (order_id,),
        )
        return cur.fetchall() or []


def compute_total(items: Iterable[Dict[str, Any]]) -> int:
    return sum(i["line_total_cents"] for i in items)
