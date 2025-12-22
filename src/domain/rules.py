# domain/rules.py
import math
from datetime import datetime, timedelta

def clamp(n, lo, hi):
    return max(lo, min(hi, n))

def compute_cutoff(now: datetime, shift_hhmm: str) -> datetime:
    cutoff = datetime.strptime(shift_hhmm, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
    if now > cutoff:
        cutoff = cutoff + timedelta(days=1)
    return cutoff

def compute_streak(now: datetime, last_relapse: datetime) -> int:
    days = math.floor((now - last_relapse).total_seconds() / 86400)
    return clamp(days, 0, 999999)