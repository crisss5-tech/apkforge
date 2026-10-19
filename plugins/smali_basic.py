"""Fallback patcher: jalan kalau template patcher 0 patch."""
import glob, os, re
from .base import BasePatcher

class SmaliBasicPatcher(BasePatcher):
    name = "smali_basic"
    HINTS = ["isPremium", "isVip", "isPro", "isSubscribed", "isPurchased", "hasSubscription"]

    def match(self, package):
        return True  # selalu bisa jalan sebagai backup

    def patch(self, decoded_dir, package):
        n = 0
        for fp in glob.glob(os.path.join(decoded_dir, "smali*", "**", "*.smali"), recursive=True):
            try:
                with open(fp) as f:
                    content = f.read()
                if not any(h in content for h in self.HINTS):
                    continue
                new = re.sub(r"(const/4\s+v\d+,\s*)0x0", r"\g<1>0x1", content)
                if new != content:
                    with open(fp, "w") as f:
                        f.write(new)
                    n += 1
            except Exception:
                pass
        return n