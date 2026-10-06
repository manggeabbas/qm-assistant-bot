#!/usr/bin/env bash
# Watchdog: pastikan hanya satu instance bot FormPelatihan-QM yang berjalan.
# Dipanggil oleh cron tiap 5 menit. Bot sendiri juga punya single-instance
# lock (output/bot.lock), jadi script ini hanya starter cadangan.
set -u
BOT_DIR="/home/hatch/workspace/formpelatihanQM"
cd "$BOT_DIR" || exit 1
mkdir -p logs

if pgrep -f "[f]ormpelatihanQM/.venv/bin/python main[.]py" >/dev/null 2>&1; then
  exit 0
fi

# Batasi ukuran log agar tidak membengkak
for f in logs/bot.log logs/watchdog.log; do
  if [ -f "$f" ] && [ "$(wc -l < "$f")" -gt 3000 ]; then
    tail -n 1000 "$f" > "$f.tmp" && mv "$f.tmp" "$f"
  fi
done

echo "$(date -Iseconds) watchdog: bot tidak berjalan, memulai ulang..." >> logs/watchdog.log
nohup "$BOT_DIR/.venv/bin/python" main.py >> logs/bot.log 2>&1 &
echo "$(date -Iseconds) watchdog: bot dimulai (pid $!)" >> logs/watchdog.log
