#!/data/data/com.termux/files/usr/bin/bash
set -e
echo "═══ crisssmods — Installer ═══"
pkg update -y && pkg upgrade -y
pkg install -y python openjdk-21 git wget unzip rust cmake make clang aapt zipalign apksigner
pip install --upgrade pip
pip install -r requirements.txt
if [ ! -d "$HOME/termux-apktool" ]; then
  git clone https://github.com/rendiix/termux-apktool.git "$HOME/termux-apktool"
fi
cd "$HOME/termux-apktool" && bash install.sh && cd "$HOME"
echo ""
echo "✅ Install selesai."
echo "→ Edit config.py (BOT_TOKEN, ADMIN_IDS)"
echo "→ bash scripts/start-api.sh  (terminal A)"
echo "→ bash scripts/start.sh      (terminal B)"