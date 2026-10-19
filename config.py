"""Konfigurasi terpusat. Semua bisa di-override via env var."""
import os

def _env(k, d): return os.getenv(k, d)

# ═══════════ IDENTITAS ═══════════
BOT_NAME    = _env("APK_BOT_NAME",   "crisssmods")
BOT_VERSION = "6.0.0"
BOT_OWNER   = _env("APK_BOT_OWNER",  "crisss5-tech")
BOT_CREDIT  = _env("APK_BOT_CREDIT", "crisssmods · @crisssmods_bot · github.com/crisss5-tech")
BOT_REPO    = _env("APK_BOT_REPO",   "https://github.com/crisss5-tech/apkforge")

# ═══════════ KREDENSIAL ═══════════
BOT_TOKEN = _env("APK_BOT_TOKEN", "8997479368:AAFCaqYUMz1tQB53rHZTubt5jUxQKrpyWz8")
API_BASE  = _env("APK_BOT_API",   "http://localhost:8081/bot")
ADMIN_IDS = [int(x) for x in _env("APK_BOT_ADMINS", "6031133192").split(",") if x.strip().isdigit()]

# ═══════════ PATH ═══════════
WORKDIR   = os.path.expanduser("~/apkbot_work")
CACHE_DIR = os.path.join(WORKDIR, "cache")
TEMP_DIR  = os.path.join(WORKDIR, "temp")
PATCHES_DIR = os.path.join(WORKDIR, "patches")
MODULES_DIR = os.path.join(WORKDIR, "modules")
LOG_DIR   = os.path.join(WORKDIR, "logs")
BACKUP_DIR = os.path.join(WORKDIR, "backups")
DB_PATH   = os.path.join(WORKDIR, "apkbot.db")
KEYSTORE  = os.path.join(WORKDIR, "release.keystore")
APKEDITOR_JAR = os.path.join(WORKDIR, "APKEditor.jar")

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
LOCALES_DIR  = os.path.join(BASE_DIR, "locales")
PLUGINS_DIR  = os.path.join(BASE_DIR, "plugins")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
BUNDLED_PATCHES = os.path.join(BASE_DIR, "patches")

# ═══════════ PARAMETER ═══════════
KS_PASS             = _env("APK_BOT_KSPASS", "crisssmods-change-me")
RATE_TIERS          = [(0, 60), (5, 45), (10, 30), (25, 15), (50, 5)]
MAX_FILE_SIZE       = 2 * 1024 ** 3
WORKERS             = 3
RETRY_ATTEMPTS      = 3
CACHE_MAX_MB        = 500
CACHE_TTL_DAYS      = 7
CLEANUP_INTERVAL_H  = 6
WATCHDOG_INTERVAL_S = 60
BREAKER_FAIL_THRESH = 3
BREAKER_COOLDOWN_S  = 300
DEFAULT_LANG        = "id"
APKEDITOR_URL       = "https://github.com/REAndroid/APKEditor/releases/download/V1.4.4/APKEditor-1.4.4.jar"

# ═══════════ WEB UI ═══════════
WEB_HOST    = _env("APK_BOT_WEBHOST", "127.0.0.1")
WEB_PORT    = int(_env("APK_BOT_WEBPORT", "8000"))
WEB_ENABLED = _env("APK_BOT_WEB", "1") == "1"

# ═══════════ MARKETPLACE ═══════════
MARKETPLACE_REPO       = _env("APK_BOT_MARKET", "https://github.com/crisss5-tech/apkforge-patches.git")
MARKETPLACE_INTERVAL_H = 12

# ═══════════ BACKUP ═══════════
BACKUP_RCLONE_REMOTE = _env("APK_BOT_RCLONE", "")
BACKUP_INTERVAL_H    = 24
BACKUP_KEEP          = 5

# ═══════════ 2FA ═══════════
ADMIN_2FA_ENABLED = True
ADMIN_2FA_TTL     = 120

# ═══════════ SELF-SETUP ═══════════
def ensure_dirs():
    for d in (WORKDIR, CACHE_DIR, TEMP_DIR, PATCHES_DIR, MODULES_DIR, LOG_DIR, BACKUP_DIR):
        os.makedirs(d, exist_ok=True)
    # Copy bundled patches ke workdir (jangan overwrite yang udah ada)
    if os.path.isdir(BUNDLED_PATCHES):
        import shutil
        for f in os.listdir(BUNDLED_PATCHES):
            if f.endswith(".json"):
                src = os.path.join(BUNDLED_PATCHES, f)
                dst = os.path.join(PATCHES_DIR, f)
                if not os.path.exists(dst):
                    try: shutil.copy(src, dst)
                    except Exception: pass

ensure_dirs()