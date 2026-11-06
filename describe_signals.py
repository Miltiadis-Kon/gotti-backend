from db.connection import pool
pool.initialize()
with pool.get_cursor() as cur:
    cur.execute("DESCRIBE signals")
    for r in cur.fetchall():
        print(r['Field'])
