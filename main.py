"""Entrypoint bot: handlers + worker + post_init."""
import os, asyncio, time, logging, threading, shutil
from telegram import Update, InputFile, InlineKeyboardButton as B, InlineKeyboardMarkup as M
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, filters, ContextTypes)

from config import *
from core import (
    Loading, init_db, upsert_user, user_get, user_set, user_hist,
    user_stats, admin_stats, rate_ok, find_apk, download_file,
    is_split, merge_split, ensure_keystore, patch_apk, diff_report,
    cache_path, cache_cleanup, get_xposed, log_req, job_save,
    job_done, jobs_pending, metric_inc, metrics_all,
    auto_update_checker, track_package, db,
)
from ui import main_menu, back_kb, nav_kb, settings_kb, confirm_kb, admin_kb
from i18n import t
from brand import header, footer, about as about_text, profile as profile_text

log = logging.getLogger("apkbot")
QUEUE = asyncio.PriorityQueue()

# ═══════════ BACKGROUND ═══════════
async def cleanup_loop():
    while True:
        try:
            cache_cleanup()
        except Exception as e:
            log.warning(f"cleanup: {e}")
        await asyncio.sleep(CLEANUP_INTERVAL_H * 3600)

async def watchdog():
    while True:
        await asyncio.sleep(WATCHDOG_INTERVAL_S)
        try:
            log.info(f"watch: {admin_stats()} q={QUEUE.qsize()}")
        except Exception:
            pass

async def market_loop():
    await asyncio.sleep(60)
    while True:
        try:
            from marketplace import sync
            await asyncio.get_event_loop().run_in_executor(None, sync)
        except Exception:
            pass
        await asyncio.sleep(MARKETPLACE_INTERVAL_H * 3600)

async def backup_loop():
    await asyncio.sleep(3600)
    while True:
        try:
            from backup import do_backup
            await asyncio.get_event_loop().run_in_executor(None, do_backup)
        except Exception:
            pass
        await asyncio.sleep(BACKUP_INTERVAL_H * 3600)

async def post_init(app):
    init_db()
    for i in range(WORKERS):
        asyncio.create_task(worker(app, i))
    asyncio.create_task(cleanup_loop())
    asyncio.create_task(watchdog())
    asyncio.create_task(auto_update_checker(app))
    asyncio.create_task(market_loop())
    asyncio.create_task(backup_loop())
    if WEB_ENABLED:
        try:
            from webui import run as web_run
            threading.Thread(target=web_run, daemon=True).start()
            log.info(f"Web UI: http://{WEB_HOST}:{WEB_PORT}")
        except Exception as e:
            log.warning(f"web: {e}")
    for jid, uid, chat, pkg, ver in jobs_pending():
        await QUEUE.put((2, time.time(), (jid, uid, chat, pkg, ver, None)))
    log.info("post_init done")

# ═══════════ WORKER ═══════════
async def worker(app, idx):
    while True:
        _, _, job = await QUEUE.get()
        jid, uid, chat, pkg, ver, load_msg = job
        try:
            load = Loading(load_msg) if load_msg else None
            if load:
                await load.start("Antrian...")
            await run_pipeline(app, uid, chat, pkg, ver, load)
            if jid:
                job_done(jid)
        except Exception as e:
            log.exception(f"worker{idx}: {e}")
        finally:
            QUEUE.task_done()

async def run_pipeline(app, uid, chat, pkg, ver, load):
    t0 = time.time()
    cached = cache_path(pkg, ver)
    if os.path.exists(cached):
        if load:
            await load.update(0.7, "Cache hit")
            await load.step("cache")
        await send_result(app, chat, pkg, ver, cached, "cache", None, None)
        log_req(uid, pkg, ver, "ok", os.path.getsize(cached), "cache", time.time() - t0)
        return

    if load:
        await load.update(0.10, "Cari sumber...")
    src, title, version, link = find_apk(pkg, ver)
    if load:
        await load.step(f"src {src}")

    if load:
        await load.update(0.25, "Unduh...")
    orig = os.path.join(TEMP_DIR, f"{pkg}_orig.apk")
    if not download_file(link, orig):
        raise RuntimeError("download gagal")
    if load:
        await load.step(f"dl {os.path.getsize(orig)//1024}KB")

    if is_split(orig):
        if load:
            await load.update(0.40, "Merge split...")
        merged = os.path.join(TEMP_DIR, f"{pkg}_m.apk")
        merge_split(orig, merged)
        orig = merged
        if load:
            await load.step("split merged")

    if load:
        await load.update(0.55, "Patch...")
    ensure_keystore()
    patched = os.path.join(TEMP_DIR, f"{pkg}_{ver}_mod.apk")
    cfg = user_get(uid)
    steps = []
    loop = asyncio.get_event_loop()
    _, n = await loop.run_in_executor(
        None,
        lambda: patch_apk(orig, patched, pkg, steps.append, cfg.get("dry_run", False))
    )
    for s in steps:
        if load:
            await load.step(s)

    if cfg.get("dry_run"):
        if load:
            await load.finish(f"🧪 **Dry-run** `{pkg}`\nPatched: `{n}` file")
        log_req(uid, pkg, ver, "dry", 0, src, time.time() - t0)
        return

    if load:
        await load.update(0.85, "Simpan cache...")
    shutil.copy(patched, cached)

    if load:
        await load.update(0.95, "Kirim...")
    diff = diff_report(orig, patched)
    xmod = get_xposed(pkg)
    await send_result(app, chat, pkg, ver, cached, src, diff, xmod)
    log_req(uid, pkg, ver, "ok", os.path.getsize(cached), src, time.time() - t0)
    metric_inc("ok")
    track_package(pkg, ver)
    for p in (orig, patched):
        try:
            os.remove(p)
        except OSError:
            pass

async def send_result(app, chat, pkg, ver, path, src, diff, xmod):
    size_mb = os.path.getsize(path) / (1024 * 1024)
    cap = f"✅ **{pkg}** v`{ver}`\n📦 `{src}` · 💾 `{size_mb:.1f} MB`"
    if diff:
        cap += f"\n🔀 `{diff.get('delta', 0)//1024:+d} KB`"
    cap += f"\n\n— {BOT_CREDIT}"
    kb = M([[B("🔄 Ulang", callback_data=f"redo:{pkg}:{ver}"),
             B("🏠 Menu", callback_data="menu:home")]])
    with open(path, "rb") as f:
        await app.bot.send_document(chat_id=chat,
                                    document=InputFile(f, filename=os.path.basename(path)),
                                    caption=cap, parse_mode="Markdown", reply_markup=kb)
    if xmod:
        with open(xmod, "rb") as f:
            await app.bot.send_document(chat_id=chat,
                                        document=InputFile(f, filename=f"{pkg}_xposed.zip"),
                                        caption=f"🧩 Xposed `{pkg}`",
                                        parse_mode="Markdown")

# ═══════════ HANDLERS ═══════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    upsert_user(u.id, u.username or u.first_name or "user")
    cfg = user_get(u.id)
    await update.message.reply_text(
        f"{header()}\n\nSelamat datang, **{u.first_name or 'user'}**!\n\n"
        f"Patch APK jadi premium, langsung dari Telegram.\n"
        f"`2 GB` · `signed` · `cache` · `queue` · `plugins`"
        f"{footer()}",
        parse_mode="Markdown",
        reply_markup=main_menu(u.id, cfg["lang"], u.id in ADMIN_IDS))

async def cmd_health(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = admin_stats()
    await update.message.reply_text(
        f"{header('Health')}\n\n"
        f"**Queue**   : `{QUEUE.qsize()}`\n"
        f"**Workers** : `{WORKERS}`\n"
        f"**Req**     : `{s['total_requests']}`\n"
        f"**Users**   : `{s['users']}`"
        f"{footer()}", parse_mode="Markdown")

async def cmd_templates(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from marketplace import list_templates
    items = list_templates()
    if not items:
        await update.message.reply_text("📋 Belum ada template patch.")
        return
    txt = "\n".join(f"• `{p}`" for p in items[:30])
    await update.message.reply_text(
        f"{header('Templates')}\n\n{txt}\n\nTotal: `{len(items)}`{footer()}",
        parse_mode="Markdown")

async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    target = int(ctx.args[0])
    user_set(target, banned=True)
    await update.message.reply_text(f"🚫 banned `{target}`", parse_mode="Markdown")

async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    target = int(ctx.args[0])
    user_set(target, banned=False)
    await update.message.reply_text(f"✅ unbanned `{target}`", parse_mode="Markdown")

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    u = update.effective_user
    cfg = user_get(u.id)
    lang = cfg["lang"]

    if d == "noop":
        return

    if d == "menu:home":
        await q.edit_message_text(
            f"{header()}\n\n{t(lang, 'menu_title')}{footer()}",
            parse_mode="Markdown",
            reply_markup=main_menu(u.id, lang, u.id in ADMIN_IDS))
    elif d == "menu:search":
        await q.edit_message_text(t(lang, "search_prompt"),
                                  parse_mode="Markdown", reply_markup=back_kb(lang))
    elif d == "menu:profile":
        st = user_stats(u.id)
        await q.edit_message_text(profile_text(u.id, cfg["username"], st),
                                  parse_mode="Markdown", reply_markup=back_kb(lang))
    elif d == "menu:settings":
        await q.edit_message_text(
            f"{header('Pengaturan')}\n\n{t(lang, 'settings_title')}{footer()}",
            parse_mode="Markdown",
            reply_markup=settings_kb(lang, cfg["theme"], cfg["dry_run"], lang))
    elif d == "settings:theme":
        user_set(u.id, theme="compact" if cfg["theme"] == "detailed" else "detailed")
        cfg = user_get(u.id)
        await q.edit_message_text(f"⚙️ theme: `{cfg['theme']}`", parse_mode="Markdown",
                                  reply_markup=settings_kb(lang, cfg["theme"], cfg["dry_run"], lang))
    elif d == "settings:dry":
        user_set(u.id, dry_run=not cfg["dry_run"])
        cfg = user_get(u.id)
        await q.edit_message_text(f"⚙️ dry-run: `{cfg['dry_run']}`", parse_mode="Markdown",
                                  reply_markup=settings_kb(lang, cfg["theme"], cfg["dry_run"], lang))
    elif d == "settings:lang":
        new = "en" if lang == "id" else "id"
        user_set(u.id, lang=new)
        lang = new
        await q.edit_message_text(f"⚙️ lang: `{lang}`", parse_mode="Markdown",
                                  reply_markup=settings_kb(lang, cfg["theme"], cfg["dry_run"], lang))
    elif d == "menu:about":
        await q.edit_message_text(about_text(), parse_mode="Markdown",
                                  reply_markup=back_kb(lang))
    elif d == "menu:history":
        hist = user_hist(u.id)
        if not hist:
            await q.edit_message_text(f"{header('Riwayat')}\n\nKosong.{footer()}",
                                      parse_mode="Markdown", reply_markup=back_kb(lang))
        else:
            await show_hist(q, hist, 0, lang)
    elif d.startswith("hist:"):
        await show_hist(q, user_hist(u.id), int(d.split(":")[1]), lang)
    elif d == "menu:admin" and u.id in ADMIN_IDS:
        await q.edit_message_text(f"{header('Admin')}{footer()}", parse_mode="Markdown",
                                  reply_markup=admin_kb(lang))
    elif d == "admin:stats" and u.id in ADMIN_IDS:
        s = admin_stats()
        await q.edit_message_text(
            f"{header('Stats')}\n\n"
            f"Users: `{s['users']}` · Banned: `{s['banned']}`\n"
            f"Req: `{s['total_requests']}` · OK: `{s['ok_requests']}`\n"
            f"Queue: `{QUEUE.qsize()}`{footer()}",
            parse_mode="Markdown", reply_markup=admin_kb(lang))
    elif d == "admin:metrics" and u.id in ADMIN_IDS:
        m = metrics_all()
        lines = "\n".join(f"`{k}`: {v}" for k, v in list(m.items())[:15]) or "empty"
        await q.edit_message_text(f"{header('Metrics')}\n\n{lines}{footer()}",
                                  parse_mode="Markdown", reply_markup=admin_kb(lang))
    elif d == "admin:cache" and u.id in ADMIN_IDS:
        n = cache_cleanup()
        await q.edit_message_text(f"🧹 cleaned `{n}` files", parse_mode="Markdown",
                                  reply_markup=admin_kb(lang))
    elif d == "admin:users" and u.id in ADMIN_IDS:
        c = db()
        c.execute("SELECT user_id,username,banned FROM users LIMIT 20")
        rows = c.fetchall(); c.close()
        txt = "\n".join(f"`{r[0]}` {r[1] or '?'} {'🚫' if r[2] else '✅'}" for r in rows) or "none"
        await q.edit_message_text(f"{header('Users')}\n\n{txt}{footer()}",
                                  parse_mode="Markdown", reply_markup=admin_kb(lang))
    elif d == "admin:backup" and u.id in ADMIN_IDS:
        if ADMIN_2FA_ENABLED:
            from twofa import request as otp_req
            code = otp_req(u.id, "backup")
            ctx.user_data["awaiting_otp"] = "backup"
            await q.edit_message_text(f"🔐 OTP dikirim ke chat:\n`{code}`", parse_mode="Markdown")
        else:
            from backup import do_backup
            path = await asyncio.get_event_loop().run_in_executor(None, do_backup)
            await q.edit_message_text(f"💾 `{os.path.basename(path or '?')}`",
                                      parse_mode="Markdown", reply_markup=admin_kb(lang))
    elif d == "admin:market" and u.id in ADMIN_IDS:
        from marketplace import sync
        n = await asyncio.get_event_loop().run_in_executor(None, sync)
        await q.edit_message_text(f"🔄 `{n}` templates synced", parse_mode="Markdown",
                                  reply_markup=admin_kb(lang))
    elif d.startswith("go:"):
        _, pkg, ver = d.split(":", 2)
        await enqueue(u, update.effective_chat.id, pkg, ver, ctx)
    elif d.startswith("redo:"):
        _, pkg, ver = d.split(":", 2)
        await enqueue(u, update.effective_chat.id, pkg, ver, ctx)

async def show_hist(q, hist, page, lang):
    per = 5
    total = max(1, (len(hist) + per - 1) // per)
    page = min(page, total - 1)
    chunk = hist[page*per:(page+1)*per]
    lines = "\n".join(f"• `{p}` v`{v}` — {s} ({d[:10]})" for p, v, s, d in chunk)
    await q.edit_message_text(
        f"{header('Riwayat')}\n\n({page+1}/{total})\n\n{lines}{footer()}",
        parse_mode="Markdown", reply_markup=nav_kb(lang, page, total, "hist"))

async def enqueue(u, chat, pkg, ver, ctx):
    cfg = user_get(u.id)
    if cfg["banned"]:
        await ctx.bot.send_message(chat, t(cfg["lang"], "banned"))
        return
    ok, wait = rate_ok(u.id, u.id in ADMIN_IDS)
    if not ok:
        await ctx.bot.send_message(chat, t(cfg["lang"], "wait", s=wait), parse_mode="Markdown")
        return
    msg = await ctx.bot.send_message(chat, "⏳", parse_mode="Markdown")
    load = Loading(msg)
    await load.start("Antrian...")
    jid = job_save(u.id, chat, pkg, ver)
    prio = 0 if u.id in ADMIN_IDS else 1
    await QUEUE.put((prio, time.time(), (jid, u.id, chat, pkg, ver, msg)))

async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    upsert_user(u.id, u.username or u.first_name or "user")
    cfg = user_get(u.id)
    lang = cfg["lang"]

    if ctx.user_data.get("awaiting_otp"):
        from twofa import verify as otp_verify
        ok, action = otp_verify(u.id, update.message.text.strip())
        ctx.user_data["awaiting_otp"] = None
        if ok and action == "backup":
            from backup import do_backup
            path = await asyncio.get_event_loop().run_in_executor(None, do_backup)
            await update.message.reply_text(f"💾 `{os.path.basename(path or '?')}`",
                                            parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ OTP salah/expired")
        return

    if cfg["banned"]:
        await update.message.reply_text(t(lang, "banned"))
        return

    txt = update.message.text.strip()
    items = [x.strip() for x in txt.split(",") if x.strip()]
    valid = [it.split(" ", 1) for it in items if " " in it]
    if not valid:
        await update.message.reply_text("Format: `nama.paket versi`",
                                        parse_mode="Markdown", reply_markup=back_kb(lang))
        return

    for pkg, ver in valid:
        load_msg = await update.message.reply_text("⏳", parse_mode="Markdown")
        load = Loading(load_msg)
        await load.start("Antrian...")
        jid = job_save(u.id, update.effective_chat.id, pkg, ver)
        prio = 0 if u.id in ADMIN_IDS else 1
        await QUEUE.put((prio, time.time(),
                         (jid, u.id, update.effective_chat.id, pkg, ver, load_msg)))

def main():
    app = (Application.builder()
           .token(BOT_TOKEN)
           .base_url(API_BASE)
           .post_init(post_init)
           .build())
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(CommandHandler("templates", cmd_templates))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    print(f"🤖 {BOT_NAME} v{BOT_VERSION} jalan. Ctrl+C stop.")
    app.run_polling()

if __name__ == "__main__":
    main()