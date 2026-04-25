# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.utils.db_utils import DatabaseUtils
conn, cur = DatabaseUtils.connect_to_mysql()

print("=" * 70)
print("[1] DB stock_daily_history 000001.SZ last 5")
print("=" * 70)
cur.execute("""
    SELECT trade_date, close, vol, amount 
    FROM stock_daily_history 
    WHERE ts_code = '000001.SZ'
    ORDER BY trade_date DESC LIMIT 5
""")
for r in cur.fetchall():
    print("  {} | close={:.2f} | vol={:.0f}(shou) | amount={:.0f}".format(r[0], r[1], r[3], r[2]))

print("")
print("=" * 70)
print("[2] DB 4/22-4/25 exists?")
print("=" * 70)
cur.execute("""
    SELECT trade_date, COUNT(*), SUM(vol) 
    FROM stock_daily_history 
    WHERE ts_code = '000001.SZ' AND trade_date >= '20260422' AND trade_date <= '20260426'
    GROUP BY trade_date ORDER BY trade_date
""")
rows = cur.fetchall()
if rows:
    for r in rows:
        print("  {} -> {} tiao, total_vol={}".format(r[0], r[1], r[2]))
else:
    print("  no data!")
conn.close()

print("")
print("=" * 70)
print("[3] Sina realtime quote volume")
print("=" * 70)

try:
    import requests as req
    session = req.Session()
    session.trust_env = False

    url = "http://hq.sinajs.cn/list=sz000001"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "http://finance.sina.com.cn",
    }
    r = session.get(url, headers=headers, timeout=10)
    if r.status_code == 200:
        text = r.text.strip()
        if len(text) > 400:
            print("  raw (first 300): {}".format(text[:300]))
        
        if "=" in text:
            data_str = text.split('="')[1].rstrip('";')
            fields = data_str.split(",")
            if len(fields) >= 30:
                sina_name   = fields[0]
                sina_open   = fields[1]
                sina_pre_close = fields[2]
                sina_price  = fields[3]
                sina_high   = fields[4]
                sina_low    = fields[5]
                sina_volume = fields[8]
                sina_amount = fields[9]

                print("")
                print("  name={}".format(sina_name))
                print("  price={}, open={}, pre_close={}".format(sina_price, sina_open, sina_pre_close))
                print("  high={}, low={}".format(sina_high, sina_low))
                print("  ** volume(chengjiaoliang)={}".format(sina_volume))
                print("  ** amount(chengjiaoe)={}".format(sina_amount))

                try:
                    vol_num = float(sina_volume)
                    print("")
                    print("  volume_num = {:.0f}".format(vol_num))
                    if vol_num > 100000000:
                        print("  !! looks like 'gu' not 'shou'!")
                        print("     if shou: {:.0f} shou".format(vol_num))
                        print("     if gu: {:.0f} gu = {:.0f} shou".format(vol_num, vol_num / 100.0))
                    else:
                        print("  OK scale (likely shou)")
                except Exception as e2:
                    print("  parse err: {}".format(e2))
except Exception as e:
    print("  sina check failed: {}".format(e))

print("")
print("=" * 70)
print("[4] Tushare pro.daily vol for 4/20-4/26")
print("=" * 70)

try:
    pro = DatabaseUtils.init_tushare_api()
    df = pro.daily(ts_code="000001.SZ", start_date="20260420", end_date="20260426")
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            t_date = str(row["trade_date"])
            t_vol = row["vol"]
            t_amount = row["amount"]
            t_close = row["close"]
            print("  {} | close={:.2f} | vol={:.0f} | amount={:.0f}".format(t_date, t_close, t_vol, t_amount))

        if len(df) >= 2:
            vols = list(df["vol"].tail(2))
            ratio = float(vols[-1]) / max(float(vols[0]), 1)
            print("")
            print("  last 2 days ratio: {:.2f}x ({:.0f} -> {:.0f})".format(ratio, vols[0], vols[-1]))
            if ratio > 5:
                print("  !! Tushare daily also shows abnormally high vol on 4/24!")
except Exception as e:
    print("  tushare check failed: {}".format(e))

print("")
print("done")
