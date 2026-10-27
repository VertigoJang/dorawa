#!/bin/bash
# Dorawa 설치 스크립트 (리눅스, systemd)
set -e

if [ "$(id -u)" -ne 0 ]; then
  echo "sudo ./install.sh 로 실행하세요."
  exit 1
fi

LIB=/usr/local/lib/dorawa
echo "[1/4] 의존성 확인 (python3, ffmpeg, nmcli)"
for c in python3 nmcli; do
  command -v "$c" >/dev/null || { echo "  필요: $c"; MISSING=1; }
done
command -v ffmpeg >/dev/null || echo "  (웹캠 기능을 쓰려면 ffmpeg 필요)"
[ -n "$MISSING" ] && { echo "필수 패키지를 먼저 설치하세요."; exit 1; }

echo "[2/4] 프로그램 복사 -> $LIB"
mkdir -p "$LIB"
cp -r dorawa/* "$LIB"/
chmod 755 "$LIB/agent.py"

echo "[3/4] systemd 유닛 설치"
cp systemd/dorawa.service systemd/dorawa.timer /etc/systemd/system/
systemctl daemon-reload

echo "[4/4] 설정 마법사 실행"
python3 "$LIB/setup.py"

echo
echo "설치 완료. 타이머를 켜려면:"
echo "  sudo systemctl enable --now dorawa.timer"
