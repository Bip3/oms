from typing import Any, Dict, List, Optional


def create_product(
    conn,
    sku: str,
    name: str,
    description: Optional[str],
    price_cents: int,
    stock_quantity: int,
    is_active: bool,
) -> Dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO products (sku, name, description, price_cents, stock_quantity, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, sku, name, description, price_cents, stock_quantity, is_active, created_at, updated_at
            """,
            (sku, name, description, price_cents, stock_quantity, is_active),
        )
        row = cur.fetchone()
    conn.commit()
    return row


def get_product_by_id(conn, product_id: int) -> Optional[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, sku, name, description, price_cents, stock_quantity, is_active, created_at, updated_at
            FROM products
            WHERE id = %s
            """,
            (product_id,),
        )
        return cur.fetchone()


def update_product(
    conn,
    product_id: int,
    name: Optional[str],
    description: Optional[str],
    price_cents: Optional[int],
    stock_quantity: Optional[int],
    is_active: Optional[bool],
) -> Optional[Dict[str, Any]]:
    fields = []
    params: List[Any] = []

    if name is not None:
        fields.append("name = %s")
        params.append(name)
    if description is not None:
        fields.append("description = %s")
        params.append(description)
    if price_cents is not None:
        fields.append("price_cents = %s")
        params.append(price_cents)
    if stock_quantity is not None:
        fields.append("stock_quantity = %s")
        params.append(stock_quantity)
    if is_active is not None:
        fields.append("is_active = %s")
        params.append(is_active)

    if not fields:
        return get_product_by_id(conn, product_id)
    params.append(product_id)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE products
            SET {", ".join(fields)}, updated_at = now()
            WHERE id = %s
            RETURNING id, sku, name, description, price_cents, stock_quantity, is_active, created_at, updated_at
            """,
            tuple(params),
        )
        row = cur.fetchone()
    conn.commit()
    return row


def delete_product(conn, product_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM products
            WHERE id = %s
            """,
            (product_id,),
        )
        deleted = cur.rowcount > 0
    conn.commit()
    return deleted
