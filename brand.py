"""Header/footer/kartu identitas."""
from config import BOT_NAME, BOT_VERSION, BOT_OWNER, BOT_CREDIT, BOT_REPO, WORKERS

def header(title=""):
    top = "╭━━━━━━━━━━━━━━━━━━━━━━╮"
    bot = f"   🤖  **{BOT_NAME}**  v{BOT_VERSION}"
    t   = f"\n   {title}" if title else ""
    botl = "╰━━━━━━━━━━━━━━━━━━━━━━╯"
    return f"{top}\n{bot}{t}\n{botl}"

def footer():
    return f"\n\n— {BOT_CREDIT}"

def card(title, body):
    return f"{header(title)}\n\n{body}{footer()}"

def about():
    return card("Tentang", (
        f"**Nama**     : `{BOT_NAME}`\n"
        f"**Versi**    : `v{BOT_VERSION}`\n"
        f"**Owner**    : `{BOT_OWNER}`\n"
        f"**Repo**     : {BOT_REPO}\n\n"
        f"**Pipeline** : src → dl → merge → patch → sign → verify → send\n"
        f"**Stack**    : FSM · plugins · queue · cache · metrics · i18n\n"
        f"**Limit**    : 2 GB upload · {WORKERS} worker · rate-adaptive"
    ))

def profile(uid, username, stats):
    return card("Profil", (
        f"**ID**       : `{uid}`\n"
        f"**Username** : `@{username or '-'}`\n"
        f"**Request**  : `{stats.get('total', 0)}`\n"
        f"**Sukses**   : `{stats.get('ok', 0)}`\n"
        f"**Gagal**    : `{stats.get('fail', 0)}`\n"
        f"**Tier**     : `{stats.get('tier', 'basic')}`"
    ))