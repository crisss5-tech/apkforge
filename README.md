# crisssmods — APK Forge v6

Bot Telegram open source untuk patch APK (premium unlock / no ads) langsung dari HP.
Jalan di **Termux**, tanpa root. Upload sampai **2 GB** via Local Bot API.

**Repo**: https://github.com/crisss5-tech/apkforge
**Bot**: @crisssmods_bot

## Fitur

- 🔍 Multi-source APK search (APKPure / APKMirror / Aptoide) + circuit breaker
- ⬇️ Download + merge split APK otomatis
- 🛠️ Patch smali (template JSON per package + fallback `_generic.json`)
- 🔐 Sign + verify (`apksigner`) — hasil pasti installable
- 💾 Cache LRU + TTL · riwayat SQLite · job resume
- 📊 Web dashboard (`http://127.0.0.1:8000`)
- 🌐 i18n ID / EN · 👤 profil · 🛡️ admin · 💾 backup · 🧪 dry-run
- ⚙️ FSM · plugins · queue priority · auto-update checker

## Setup Termux

```bash
pkg update && pkg upgrade -y
pkg install python openjdk-21 git wget unzip rust cmake make clang aapt zipalign apksigner -y
git clone https://github.com/crisss5-tech/apkforge.git ~/apkforge
cd ~/apkforge
pip install -r requirements.txt
bash scripts/install.sh