#!/usr/bin/env python3
"""Verify XAUUSD tick CSVs: row counts, spread positivity, data gaps."""
import csv, glob, os, sys
from datetime import datetime, timezone

# Weekend close (Fri 21:55 UTC) to Sun 22:05 UTC — expected gap
WEEKEND_SEC = 2 * 86400

def is_weekend_gap(a_ms, b_ms):
    da = datetime.fromtimestamp(a_ms/1000, tz=timezone.utc)
    db = datetime.fromtimestamp(b_ms/1000, tz=timezone.utc)
    # Friday(4) after 21:00 UTC through Sunday(6) before 23:00 UTC
    def fridfut(d): return d.weekday() == 4 and d.hour >= 21
    def sunearly(d): return d.weekday() == 6 and d.hour <= 23
    return (fridfut(da) or da.weekday() == 5 or sunearly(da)) and \
           (sunearly(db) or db.weekday() == 5 or fridfut(db))

for f in sorted(glob.glob('download/xauusd-tick-*.csv')):
    year = os.path.basename(f).split('-')[2]
    n = 0; bad_spread = 0; gaps = []; prev = None; first = last = None
    with open(f, newline='') as fh:
        r = csv.reader(fh)
        next(r)
        for row in r:
            ts = int(row[0]); ask = float(row[1]); bid = float(row[2])
            n += 1
            if ask - bid <= 0:
                bad_spread += 1
            if prev is not None and ts - prev > 60_000:  # >1 min gap
                if not is_weekend_gap(prev, ts):
                    gaps.append((datetime.fromtimestamp(prev/1000, timezone.utc).isoformat(),
                                 datetime.fromtimestamp(ts/1000, timezone.utc).isoformat(),
                                 (ts-prev)/1000))
            if first is None: first = ts
            last = ts
            prev = ts
    print(f"{year}: rows={n:,} bad_spread={bad_spread} nonweekend_gaps>60s={len(gaps)} "
          f"first={datetime.fromtimestamp(first/1000, timezone.utc)} last={datetime.fromtimestamp(last/1000, timezone.utc)}")
    for g in gaps[:10]:
        print("   gap:", g)
    sys.stdout.flush()
