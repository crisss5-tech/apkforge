import json, os
from config import LOCALES_DIR, DEFAULT_LANG

_cache = {}
for f in os.listdir(LOCALES_DIR):
    if f.endswith(".json"):
        try:
            with open(os.path.join(LOCALES_DIR, f), encoding="utf-8") as fh:
                _cache[f[:-5]] = json.load(fh)
        except Exception:
            pass

def t(lang, key, **kw):
    val = _cache.get(lang, {}).get(key) or _cache[DEFAULT_LANG].get(key, key)
    return val.format(**kw) if kw else val