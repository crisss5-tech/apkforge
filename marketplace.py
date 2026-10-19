import os, subprocess, shutil, glob, logging
from config import PATCHES_DIR, MARKETPLACE_REPO

log = logging.getLogger("marketplace")
CLONE_DIR = os.path.join(PATCHES_DIR, ".repo")

def sync():
    if not MARKETPLACE_REPO:
        return 0
    try:
        if not os.path.exists(CLONE_DIR):
            subprocess.run(["git", "clone", "--depth", "1", MARKETPLACE_REPO, CLONE_DIR],
                           check=True, capture_output=True, timeout=120)
        else:
            subprocess.run(["git", "-C", CLONE_DIR, "pull", "--ff-only"],
                           check=True, capture_output=True, timeout=120)
        n = 0
        for f in glob.glob(os.path.join(CLONE_DIR, "*.json")):
            shutil.copy(f, os.path.join(PATCHES_DIR, os.path.basename(f)))
            n += 1
        return n
    except Exception as e:
        log.warning(f"marketplace: {e}")
        return 0

def list_templates():
    return sorted(
        f[:-5] for f in os.listdir(PATCHES_DIR)
        if f.endswith(".json") and not f.startswith(".")
    )