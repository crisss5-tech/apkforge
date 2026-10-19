import importlib, pkgutil, os
from .base import BasePatcher

def load_plugins():
    out = []
    pkg_dir = os.path.dirname(__file__)
    for _, mod, _ in pkgutil.iter_modules([pkg_dir]):
        if mod in ("base", "__init__"):
            continue
        try:
            m = importlib.import_module(f"plugins.{mod}")
            for attr in dir(m):
                obj = getattr(m, attr)
                if isinstance(obj, type) and issubclass(obj, BasePatcher) and obj is not BasePatcher:
                    try:
                        out.append(obj())
                    except Exception:
                        pass
        except Exception:
            pass
    return out