from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup as M
from i18n import t

def main_menu(uid, lang, is_admin=False):
    rows = [
        [B(t(lang, "menu_search"), callback_data="menu:search")],
        [B(t(lang, "menu_history"), callback_data="menu:history"),
         B(t(lang, "menu_profile"), callback_data="menu:profile")],
        [B(t(lang, "menu_settings"), callback_data="menu:settings"),
         B(t(lang, "menu_about"), callback_data="menu:about")],
    ]
    if is_admin:
        rows.append([B(t(lang, "menu_admin"), callback_data="menu:admin")])
    return M(rows)

def back_kb(lang, target="menu:home"):
    return M([[B("◀  Kembali", callback_data=target),
               B("🏠  Menu", callback_data="menu:home")]])

def nav_kb(lang, page, total, prefix):
    row = []
    if page > 0:
        row.append(B("◀", callback_data=f"{prefix}:{page-1}"))
    row.append(B(f"{page+1}/{total}", callback_data="noop"))
    if page < total - 1:
        row.append(B("▶", callback_data=f"{prefix}:{page+1}"))
    return M([row, [B("🏠  Menu", callback_data="menu:home")]])

def settings_kb(lang, theme, dry, cur_lang):
    return M([
        [B(f"{t(lang,'theme_switch')}: {theme}", callback_data="settings:theme")],
        [B(f"{t(lang,'dry_run')}: {'ON' if dry else 'OFF'}", callback_data="settings:dry")],
        [B(f"{t(lang,'lang_switch')}: {cur_lang.upper()}", callback_data="settings:lang")],
        [B("◀  Kembali", callback_data="menu:home")],
    ])

def confirm_kb(lang, pkg, ver):
    return M([[B(t(lang, "yes"), callback_data=f"go:{pkg}:{ver}"),
               B(t(lang, "no"), callback_data="menu:home")]])

def admin_kb(lang):
    return M([
        [B("📊 Stats", callback_data="admin:stats"),
         B("🧹 Cache", callback_data="admin:cache")],
        [B("👥 Users", callback_data="admin:users"),
         B("📈 Metrics", callback_data="admin:metrics")],
        [B("💾 Backup", callback_data="admin:backup"),
         B("🔄 Market", callback_data="admin:market")],
        [B("◀  Kembali", callback_data="menu:home")],
    ])