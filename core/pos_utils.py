from django.db import connection

def get_terminal_by_api_key(api_key: str):
    if not api_key:
        return None
    with connection.cursor() as cur:
        cur.execute("""
            SELECT pt.id, pt.code, m.name, m.category
            FROM pos_terminal pt
            JOIN merchant m ON m.id = pt.merchant_id
            WHERE pt.api_key=%s AND pt.active=TRUE AND m.active=TRUE
            LIMIT 1
        """, [api_key])
        row = cur.fetchone()
    if not row:
        return None
    return {"id": row[0], "code": row[1], "merchant": row[2], "category": row[3]}

def terminal_allows_voucher(terminal_id, voucher_type_id) -> bool:
    with connection.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM pos_terminal_voucher
            WHERE terminal_id=%s AND voucher_type_id=%s
            LIMIT 1
        """, [str(terminal_id), str(voucher_type_id)])
        return cur.fetchone() is not None
