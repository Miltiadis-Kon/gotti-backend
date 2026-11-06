from db.connection import pool
pool.initialize()
with pool.get_cursor() as cur:
    cur.execute("SELECT signal_id, ticker, signal_date, signal_position, created_at, metadata FROM signals WHERE ticker IN ('JELD', 'QCOM', 'GOGO', 'HIMS', 'FIGS', 'SES', 'OCGN') ORDER BY created_at DESC LIMIT 10")
    for r in cur.fetchall():
        print(r['signal_id'], r['ticker'], r['signal_position'], r['created_at'], r['metadata'])
