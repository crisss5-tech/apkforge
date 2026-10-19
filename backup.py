import os, sqlite3, subprocess, logging
from datetime import datetime
from config import DB_PATH, PATCHES_DIR, BACKUP_DIR, BACKUP_KEEP, BACKUP_RCLONE_REMOTE

log = logging.getLogger("backup")

def do_backup():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp = os.path.join(BACKUP_DIR, f"apkbot_{ts}.db")
    try:
        src = sqlite3.connect(DB_PATH)
        dst = sqlite3.connect(tmp)
        src.backup(dst)
        dst.close(); src.close()
    except Exception as e:
        log.warning(f"backup db: {e}")
        return None
    try:
        subprocess.run(["tar", "-czf",
                        os.path.join(BACKUP_DIR, f"patches_{ts}.tar.gz"),
                        "-C", PATCHES_DIR, "."],
                       check=False, capture_output=True, timeout=120)
    except Exception:
        pass
    files = sorted(f for f in os.listdir(BACKUP_DIR)
                   if f.startswith("apkbot_") and f.endswith(".db"))
    for f in files[:-BACKUP_KEEP]:
        try: os.remove(os.path.join(BACKUP_DIR, f))
        except OSError: pass
    if BACKUP_RCLONE_REMOTE:
        try:
            subprocess.run(["rclone", "copy", tmp, BACKUP_RCLONE_REMOTE],
                           check=False, timeout=180, capture_output=True)
        except Exception as e:
            log.warning(f"rclone: {e}")
    return tmp