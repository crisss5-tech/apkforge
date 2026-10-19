import random, time
from config import ADMIN_IDS, ADMIN_2FA_TTL

_pending = {}

def request(uid, action):
    if uid not in ADMIN_IDS:
        return None
    code = f"{random.randint(100000, 999999)}"
    _pending[uid] = (code, time.time() + ADMIN_2FA_TTL, action)
    return code

def verify(uid, code):
    p = _pending.get(uid)
    if not p:
        return False, None
    c, exp, action = p
    if time.time() > exp:
        _pending.pop(uid, None)
        return False, None
    if c != code:
        return False, None
    _pending.pop(uid, None)
    return True, action