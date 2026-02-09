from typing import Optional, Dict, Any
import psycopg2
#--Methods--
#Create Customer
#Get Customer by ID
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