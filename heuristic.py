"""Scorer smali (pengganti ML, ringan untuk HP)."""
import re, glob, os

HINTS = {
    "isPremium": 5, "isVip": 5, "isPro": 5,
    "hasSubscription": 4, "isSubscribed": 4, "isPurchased": 4,
    "getSubscriptionType": 3, "premiumUntil": 3,
    "LicenseManager": 3, "BillingHelper": 2, "checkLicense": 3,
}

def score_smali(path):
    try:
        content = open(path, errors="ignore").read()
    except OSError:
        return 0
    if len(content) > 200_000:
        return 0
    score = sum(content.count(k) * w for k, w in HINTS.items())
    score += len(re.findall(r"const/4\s+v\d+,\s*0x0", content))
    return min(score, 20)

def suggest(decoded_dir, top_n=10):
    out = []
    for fp in glob.glob(os.path.join(decoded_dir, "smali*", "**", "*.smali"), recursive=True):
        s = score_smali(fp)
        if s >= 3:
            out.append((s, fp.replace(decoded_dir + "/", "")))
    out.sort(reverse=True)
    return out[:top_n]