#!/data/data/com.termux/files/usr/bin/bash
API_ID="${API_ID:-ISI_API_ID}"
API_HASH="${API_HASH:-ISI_API_HASH}"
cd "$HOME/telegram-bot-api/build" 2>/dev/null || {
  echo "Compile dulu:"
  echo "  git clone --recursive https://github.com/tdlib/telegram-bot-api.git ~/telegram-bot-api"
  echo "  cd ~/telegram-bot-api && mkdir build && cd build"
  echo "  cmake -DCMAKE_BUILD_TYPE=Release .. && cmake --build . --target telegram-bot-api -j\$(nproc)"
  exit 1
}
./telegram-bot-api --api-id="$API_ID" --api-hash="$API_HASH" --local --http-port=8081