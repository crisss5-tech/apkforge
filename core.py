"""Backend utama: loading, DB, cache, sources, patcher, queue helpers."""
import os, time, shutil, sqlite3, logging, subprocess, asyncio, zipfile, hashlib, re
from datetime import datetime
from logging.handlers import RotatingFileHandler

from config import *
from plugins import load_plugins

_h = RotatingFileHandler(os.path.join(LOG_DIR, "apkbot.log"),
                         maxBytes=5 * 1024 * 1024, backupCount=3)
_h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_h, logging.StreamHandler()])
log = logging.getLogger("apkbot")

# ═══════════════ LOADING ═══════════════
SPIN = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

class Loading:
    def __init__(self, message):
        self.msg = message
        self.progress = 0.0
        self.status = "…"
        self.steps = []
        self.frame = 0
        self._stop = False
        self._task = None

    def _render(self):
        w = 20
        f = int(w * self.progress)
        bar = "█" * f + "░" * (w - f)
        steps = "\n".join(f"✓ {s}" for s in self.steps[-5:])
        return (f"{SPIN[self.frame % len(SPIN)]} **{self.status}**\n"
                f"`[{bar}]` **{int(self.progress * 100)}%**"
                + ("\n\n" + steps if steps else ""))

    async def _loop(self):
        last = -1
        while not self._stop:
            try:
                p = int(self.progress * 100)
                if p != last or self.frame % 3 == 0:
                    await self.msg.edit_text(self._render(), parse_mode="Markdown")
                    last = p
                self.frame += 1
                await asyncio.sleep(0.4)
            except Exception:
                pass

    async def start(self, status="…"):
        self.status = status
        self._task = asyncio.create_task(self._loop())

    async def update(self, progress, status):
        self.progress = min(max(progress, 0.0), 1.0)
        self.status = status

    async def step(self, name):
        self.steps.append(name)

    async def finish(self, text):
        self._stop = True
        if self._task:
            await self._task
        try:
            await self.msg.edit_text(text, parse_mode="Markdown")
        except Exception:
            pass

    async def fail(self, text):
        await self.finish(text)

# ═══════════════ DB ═══════════════
def db():
    c = sqlite3.connect(DB_PATH)
    c.execute("PRAGMA journal_mode=WAL")
    return c

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, package TEXT, version TEXT, status TEXT,
        size INTEGER, source TEXT, duration REAL, created_at TEXT);
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY, username TEXT,
        lang TEXT DEFAULT 'id', theme TEXT DEFAULT 'detailed',
        banned INTEGER DEFAULT 0, dry_run INTEGER DEFAULT 0,
        first_seen TEXT, last_seen TEXT);
    CREATE TABLE IF NOT EXISTS jobs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, chat_id INTEGER, package TEXT, version TEXT,
        status TEXT DEFAULT 'queued', created_at TEXT);
    CREATE TABLE IF NOT EXISTS metrics(k TEXT PRIMARY KEY, v INTEGER DEFAULT 0);
    """)
    c.commit(); c.close()

def log_req(uid, pkg, ver, status, size, src, dur):
    c = db()
    c.execute("INSERT INTO requests(user_id,package,version,status,size,source,duration,created_at) "
              "VALUES (?,?,?,?,?,?,?,?)",
              (uid, pkg, ver, status, size, src, dur, datetime.now().isoformat()))
    c.commit(); c.close()

def upsert_user(uid, name):
    c = db(); now = datetime.now().isoformat()
    c.execute("INSERT INTO users(user_id,username,first_seen,last_seen) VALUES (?,?,?,?) "
              "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,last_seen=excluded.last_seen",
              (uid, name, now, now))
    c.commit(); c.close()

def user_get(uid):
    c = db()
    c.execute("SELECT lang,theme,banned,dry_run,username FROM users WHERE user_id=?", (uid,))
    r = c.fetchone(); c.close()
    if not r:
        return {"lang": DEFAULT_LANG, "theme": "detailed",
                "banned": False, "dry_run": False, "username": "-"}
    return {"lang": r[0], "theme": r[1], "banned": bool(r[2]),
            "dry_run": bool(r[3]), "username": r[4] or "-"}

def user_set(uid, **kw):
    c = db()
    for k, v in kw.items():
        if isinstance(v, bool):
            v = int(v)
        c.execute(f"UPDATE users SET {k}=? WHERE user_id=?", (v, uid))
    c.commit(); c.close()

def user_hist(uid, limit=20):
    c = db()
    c.execute("SELECT package,version,status,created_at FROM requests "
              "WHERE user_id=? ORDER BY id DESC LIMIT ?", (uid, limit))
    r = c.fetchall(); c.close(); return r

def user_stats(uid):
    c = db()
    c.execute("SELECT COUNT(*), SUM(status='ok'), SUM(status='fail') "
              "FROM requests WHERE user_id=?", (uid,))
    r = c.fetchone(); c.close()
    total, ok, fail = (r[0] or 0, r[1] or 0, r[2] or 0)
    tier = "basic"
    for th, name in [(50, "vip"), (25, "pro"), (10, "plus"), (5, "active")]:
        if ok >= th:
            tier = name
            break
    return {"total": total, "ok": ok, "fail": fail, "tier": tier}

def admin_stats():
    c = db()
    c.execute("SELECT COUNT(*), SUM(status='ok') FROM requests")
    tot, ok = c.fetchone()
    c.execute("SELECT COUNT(*) FROM users"); u = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE banned=1"); b = c.fetchone()[0]
    c.close()
    return {"total_requests": tot or 0, "ok_requests": ok or 0,
            "users": u or 0, "banned": b or 0}

def job_save(uid, chat, pkg, ver):
    c = db()
    c.execute("INSERT INTO jobs(user_id,chat_id,package,version,created_at) "
              "VALUES (?,?,?,?,?)", (uid, chat, pkg, ver, datetime.now().isoformat()))
    c.commit(); lid = c.lastrowid; c.close()
    return lid

def job_done(jid):
    c = db(); c.execute("UPDATE jobs SET status='done' WHERE id=?", (jid,))
    c.commit(); c.close()

def jobs_pending():
    c = db()
    c.execute("SELECT id,user_id,chat_id,package,version FROM jobs WHERE status='queued'")
    r = c.fetchall(); c.close(); return r

def metric_inc(k, n=1):
    c = db()
    c.execute("INSERT INTO metrics(k,v) VALUES (?,?) "
              "ON CONFLICT(k) DO UPDATE SET v=v+?", (k, n, n))
    c.commit(); c.close()

def metrics_all():
    c = db(); c.execute("SELECT k,v FROM metrics")
    r = dict(c.fetchall()); c.close(); return r

# ═══════════════ RATE ═══════════════
_last = {}
def rate_tier(uid, is_admin=False):
    if is_admin:
        return 0
    ok = user_stats(uid)["ok"]
    for th, sec in sorted(RATE_TIERS, key=lambda x: -x[0]):
        if ok >= th:
            return sec
    return 60

def rate_ok(uid, is_admin=False):
    limit = rate_tier(uid, is_admin)
    if limit == 0:
        return True, 0
    now = time.time()
    if uid in _last and now - _last[uid] < limit:
        return False, int(limit - (now - _last[uid]))
    _last[uid] = now
    return True, 0

# ═══════════════ BREAKER ═══════════════
class Breaker:
    def __init__(self):
        self.fail = {}
        self.open = {}
    def ok(self, name):
        if name in self.open and time.time() < self.open[name]:
            return False
        self.open.pop(name, None)
        return True
    def record(self, name, success):
        if success:
            self.fail[name] = 0
            self.open.pop(name, None)
        else:
            self.fail[name] = self.fail.get(name, 0) + 1
            if self.fail[name] >= BREAKER_FAIL_THRESH:
                self.open[name] = time.time() + BREAKER_COOLDOWN_S

breaker = Breaker()

# ═══════════════ SOURCES ═══════════════
def _sources():
    out = []
    for mod in ["APKPure", "APKMirror", "Aptoide"]:
        try:
            m = __import__("apksearch", fromlist=[mod])
            out.append((mod, getattr(m, mod)))
        except Exception:
            pass
    return out

def find_apk(pkg, ver=None):
    srcs = _sources()
    if not srcs:
        raise RuntimeError("apksearch belum terpasang: pip install apksearch")
    for name, cls in srcs:
        if not breaker.ok(name):
            continue
        try:
            r = cls(pkg).search_apk()
            link = title = None
            version = ver or "?"
            if isinstance(r, dict):
                link = r.get("download_link") or r.get("link")
                version = r.get("version", version)
                title = r.get("name", pkg)
            elif isinstance(r, (tuple, list)) and len(r) >= 2:
                title, link = r[0], r[1]
            if link:
                breaker.record(name, True)
                metric_inc(f"source_{name}_ok")
                return name, title or pkg, version, link
            breaker.record(name, False)
        except Exception as e:
            breaker.record(name, False)
            log.warning(f"{name}: {e}")
    raise RuntimeError(f"{pkg} tidak ditemukan di semua sumber")

# ═══════════════ DOWNLOAD ═══════════════
def download_file(url, out, attempts=RETRY_ATTEMPTS):
    for i in range(attempts):
        try:
            r = subprocess.run(["wget", "-q", "-O", out, url], timeout=900)
            if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 1024:
                return True
        except Exception as e:
            log.warning(f"download {i+1}/{attempts}: {e}")
        time.sleep(2 ** i)
    return False

# ═══════════════ SPLIT APK ═══════════════
def is_split(path):
    if path.lower().endswith((".apks", ".xapk", ".apkm")):
        return True
    try:
        with zipfile.ZipFile(path) as z:
            return any(n.endswith(".apk") for n in z.namelist())
    except Exception:
        return False

def ensure_apkeditor():
    if os.path.exists(APKEDITOR_JAR):
        return
    if not download_file(APKEDITOR_URL, APKEDITOR_JAR):
        raise RuntimeError("APKEditor download gagal")

def merge_split(inp, out):
    ensure_apkeditor()
    subprocess.run(["java", "-jar", APKEDITOR_JAR, "m", "-i", inp, "-o", out, "-f"],
                   check=True, capture_output=True)

# ═══════════════ KEYSTORE ═══════════════
def ensure_keystore():
    if os.path.exists(KEYSTORE):
        return
    subprocess.run([
        "keytool", "-genkey", "-v", "-keystore", KEYSTORE,
        "-alias", "apkforge", "-keyalg", "RSA", "-keysize", "2048",
        "-validity", "10000", "-storepass", KS_PASS, "-keypass", KS_PASS,
        "-dname", "CN=crisssmods, OU=Mod, O=crisss, L=ID, ST=ID, C=ID"
    ], check=True)

# ═══════════════ APK INFO ═══════════════
def apk_info(path):
    try:
        r = subprocess.run(["aapt", "dump", "badging", path],
                           capture_output=True, text=True, timeout=30)
        pkg = re.search(r"package: name='([^']+)'", r.stdout)
        ver = re.search(r"versionName='([^']+)'", r.stdout)
        perms = len(re.findall(r"uses-permission:", r.stdout))
        minsdk = re.search(r"sdkVersion:'(\d+)'", r.stdout)
        return {
            "package": pkg.group(1) if pkg else "?",
            "version": ver.group(1) if ver else "?",
            "perms": perms,
            "minsdk": minsdk.group(1) if minsdk else "?",
        }
    except Exception:
        return {}

def sig_sha256(path):
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    except OSError:
        return "?"

# ═══════════════ PATCHER ═══════════════
_patchers = None
def patchers():
    global _patchers
    if _patchers is None:
        _patchers = load_plugins()
    return _patchers

def patch_apk(original, out, pkg, cb=None, dry_run=False):
    decoded = os.path.join(TEMP_DIR, f"d_{pkg}")
    unsigned = os.path.join(TEMP_DIR, f"u_{pkg}.apk")
    aligned = os.path.join(TEMP_DIR, f"a_{pkg}.apk")
    if os.path.exists(decoded):
        shutil.rmtree(decoded)
    try:
        subprocess.run(["apktool", "d", "-f", original, "-o", decoded],
                       check=True, capture_output=True)
        if cb: cb("decode")

        # Urutkan patcher: template dulu, smali_basic cuma jalan kalau template 0
        total = 0
        for p in patchers():
            if not p.match(pkg):
                continue
            try:
                n = p.patch(decoded, pkg)
                if cb: cb(f"{p.name}: {n} file")
                total += n
                if n > 0 and p.name == "template":
                    break  # template sukses → skip smali_basic
            except Exception as e:
                log.warning(f"patcher {p.name}: {e}")

        if dry_run:
            try:
                from heuristic import suggest
                top = suggest(decoded, 5)
                if cb: cb(f"suggest: {len(top)} files")
            except Exception:
                pass
            if cb: cb("DRY-RUN skip rebuild")
            return None, total

        subprocess.run(["apktool", "b", decoded, "-o", unsigned],
                       check=True, capture_output=True)
        if cb: cb("rebuild")

        subprocess.run(["zipalign", "-f", "4", unsigned, aligned],
                       check=True, capture_output=True)
        if cb: cb("align")

        subprocess.run(["apksigner", "sign", "--ks", KEYSTORE,
                        "--ks-pass", f"pass:{KS_PASS}", "--out", out, aligned],
                       check=True, capture_output=True)
        if cb: cb("sign")

        r = subprocess.run(["apksigner", "verify", out], capture_output=True)
        if r.returncode != 0:
            raise RuntimeError("signature verify gagal")
        if cb: cb("verify")
        return out, total
    finally:
        for x in (decoded, unsigned, aligned):
            try:
                shutil.rmtree(x) if os.path.isdir(x) else os.remove(x)
            except OSError:
                pass

def diff_report(orig, patch):
    try:
        s1, s2 = os.path.getsize(orig), os.path.getsize(patch)
        return {"orig_size": s1, "new_size": s2, "delta": s2 - s1,
                "orig_sha": sig_sha256(orig)[:16],
                "new_sha": sig_sha256(patch)[:16]}
    except OSError:
        return {}

# ═══════════════ CACHE ═══════════════
def cache_path(pkg, ver):
    return os.path.join(CACHE_DIR, f"{pkg}_{ver}.apk")

def cache_cleanup():
    now = time.time()
    removed = 0
    for f in os.listdir(CACHE_DIR):
        fp = os.path.join(CACHE_DIR, f)
        try:
            if (now - os.path.getmtime(fp)) / 86400 > CACHE_TTL_DAYS:
                os.remove(fp); removed += 1
        except OSError:
            pass
    files = [os.path.join(CACHE_DIR, f) for f in os.listdir(CACHE_DIR)
             if os.path.isfile(os.path.join(CACHE_DIR, f))]
    total = sum(os.path.getsize(f) for f in files)
    if total > CACHE_MAX_MB * 1024 * 1024:
        files.sort(key=os.path.getmtime)
        for f in files:
            if total <= CACHE_MAX_MB * 1024 * 1024:
                break
            try:
                sz = os.path.getsize(f)
                os.remove(f)
                total -= sz; removed += 1
            except OSError:
                pass
    return removed

# ═══════════════ MODULES ═══════════════
def get_xposed(pkg):
    for ext in (".zip", ".apk"):
        p = os.path.join(MODULES_DIR, pkg + ext)
        if os.path.exists(p):
            return p
    return None

# ═══════════════ AUTO-UPDATE ═══════════════
_auto_track = {}
def track_package(pkg, ver):
    _auto_track[pkg] = ver

async def auto_update_checker(app):
    while True:
        await asyncio.sleep(6 * 3600)
        for pkg, known in list(_auto_track.items()):
            try:
                _, _, new_ver, _ = find_apk(pkg)
                if new_ver != known:
                    c = db()
                    c.execute("SELECT DISTINCT user_id FROM requests "
                              "WHERE package=? AND status='ok'", (pkg,))
                    users = [r[0] for r in c.fetchall()]; c.close()
                    for uid in users:
                        try:
                            await app.bot.send_message(
                                uid,
                                f"🔔 Update `{pkg}` v`{new_ver}` (lama `{known}`)",
                                parse_mode="Markdown")
                        except Exception:
                            pass
                    _auto_track[pkg] = new_ver
            except Exception:
                pass