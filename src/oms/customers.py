from typing import Optional, Dict, Any, List
import psycopg2
#--Methods--
#Create Customer
#Get Customer by ID
#Update Customer
#Delete Customer
def create_customer(
        conn,
        email: str,
        first_name: str,
        last_name: str,
        phone: Optional[str],
)-> Dict[str, Any]:
    
    #Context manager with conn.cursor() as cur =  dont have to close
    with conn.cursor() as cur:
        cur.execute(
            #%s to prevent sql injections
            """
            INSERT INTO customers (email, first_name, last_name, phone)
            VALUES (%s, %s, %s, %s)
            RETURNING id, email, first_name, last_name, phone, created_at, updated_at
            """,
            (email, first_name, last_name, phone),
        )
        row = cur.fetchone()

    conn.commit()
    return row

def get_customer_by_id(conn, customer_id: int) -> Optional[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, email, first_name, last_name, phone, created_at, updated_at
            FROM customers
            WHERE id = %s
            """,
            (customer_id,),
        )
        return cur.fetchone()

def update_customer(
        conn,
        customer_id: int,
        email: Optional[str],
        first_name: Optional[str],
        last_name: Optional[str],
        phone: Optional[str],
) -> Optional[Dict[str, Any]]:
    fields = []
    params: List[Any] = []

    if email is not None:
        fields.append("email = %s")
        params.append(email)
    if first_name is not None:
        fields.append("first_name = %s")
        params.append(first_name)
    if last_name is not None:
        fields.append("last_name = %s")
        params.append(last_name)
    if phone is not None:
        fields.append("phone = %s")
        params.append(phone)

    if not fields:
        return get_customer_by_id(conn, customer_id)

    params.append(customer_id)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE customers
            SET {", ".join(fields)}, updated_at = now()
            WHERE id = %s
            RETURNING id, email, first_name, last_name, phone, created_at, updated_at
            """,
            tuple(params),
        )
        row = cur.fetchone()
    conn.commit()
    return row

def delete_customer(conn, customer_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM customers
            WHERE id = %s
            """,
            (customer_id,),
        )
        deleted = cur.rowcount > 0
    conn.commit()
    return deleted
