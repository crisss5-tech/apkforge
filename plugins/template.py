"""Template patcher: pakai <pkg>.json kalau ada, fallback ke _generic.json."""
import json, os, glob, logging
from .base import BasePatcher
from config import PATCHES_DIR

log = logging.getLogger("plugin.template")

class TemplatePatcher(BasePatcher):
    name = "template"

    def _load(self, pkg):
        for name in (f"{pkg}.json", "_generic.json"):
            p = os.path.join(PATCHES_DIR, name)
            if os.path.exists(p):
                try:
                    with open(p) as f:
                        return json.load(f)
                except Exception as e:
                    log.warning(f"load {name}: {e}")
        return None

    def match(self, package):
        # Selalu match — fallback generic menjamin selalu ada template
        return self._load(package) is not None

    def patch(self, decoded_dir, package):
        tpl = self._load(package)
        if not tpl:
            return 0
        n = 0
        for rule in tpl.get("patches", []):
            pattern = rule.get("file_pattern")
            find    = rule.get("find")
            replace = rule.get("replace")
            if not all([pattern, find, replace]):
                continue
            hint = rule.get("method_hint")
            for fp in glob.glob(os.path.join(decoded_dir, pattern), recursive=True):
                try:
                    with open(fp) as f:
                        content = f.read()
                    if hint and hint not in content:
                        continue
                    new = content.replace(find, replace)
                    if new != content:
                        with open(fp, "w") as f:
                            f.write(new)
                        n += 1
                except Exception as e:
                    log.warning(f"patch {fp}: {e}")
        return n