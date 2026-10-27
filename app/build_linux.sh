#!/bin/bash
# Dorawa 노트북 앱 — 리눅스 실행본 빌드 (PyInstaller onefile)
set -e
cd "$(dirname "$0")"

echo "[1/4] 가상환경 준비"
python3 -m venv .venv
. .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt pyinstaller

echo "[2/4] 빌드 전 점검 (import·문법)"
python -c "import main, api, agent_ctl; print('  모듈 import OK')"

echo "[3/4] PyInstaller 빌드"
pyinstaller --clean --noconfirm dorawa.spec

echo "[4/4] 결과"
ls -lh dist/Dorawa
echo
echo "빌드 완료: dist/Dorawa"
echo "실행: ./dist/Dorawa  (또는 더블클릭)"
