#!/bin/bash
# 리눅스에서 Dorawa 아이콘을 시스템에 등록 (작업표시줄·런처에 아이콘 표시)
# 빌드한 dist/Dorawa 를 설치하고, .desktop + 아이콘을 사용자 영역에 둔다.
set -e
cd "$(dirname "$0")"

BIN="$HOME/.local/bin/Dorawa"
ICON_DIR="$HOME/.local/share/icons/hicolor"
DESKTOP="$HOME/.local/share/applications/dorawa.desktop"

echo "[1/3] 실행 파일 설치 -> $BIN"
mkdir -p "$HOME/.local/bin"
if [ -f dist/Dorawa ]; then
  cp dist/Dorawa "$BIN"
else
  echo "  dist/Dorawa 가 없습니다. 먼저 ./build_linux.sh 를 실행하세요."
  exit 1
fi
chmod +x "$BIN"

echo "[2/3] 아이콘 설치 (여러 크기)"
for sz in 256 512; do
  d="$ICON_DIR/${sz}x${sz}/apps"
  mkdir -p "$d"
  # app/icon.png 는 256. 더 큰 건 assets 에서
  if [ "$sz" = "256" ]; then cp icon.png "$d/dorawa.png"
  elif [ -f ../assets/dorawa_512.png ]; then cp ../assets/dorawa_512.png "$d/dorawa.png"
  fi
done

echo "[3/3] .desktop 등록 -> $DESKTOP"
mkdir -p "$(dirname "$DESKTOP")"
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=Dorawa
Comment=노트북 도난 추적기
Exec=$BIN
Icon=dorawa
Terminal=false
Categories=Utility;Security;
StartupWMClass=Dorawa
EOF

# 아이콘 캐시 갱신 (있으면)
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache "$ICON_DIR" 2>/dev/null || true
command -v update-desktop-database >/dev/null && update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo
echo "완료. 런처(앱 목록)에서 'Dorawa'를 찾아 실행하면 아이콘이 보입니다."
echo "작업표시줄 아이콘이 바로 안 바뀌면 로그아웃 후 재로그인하세요."
