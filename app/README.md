# Dorawa 노트북 앱 (리눅스/윈도우)

도난 추적기 Dorawa의 데스크톱 앱. 세컨드 노트북·데스크탑에서 사용.
탭 2개:
- **내 기기 추적**: 로그인 후 도난당한 기기의 위치·사진·영상 조회, 도난 모드 켜기, 원격 촬영
- **이 기기 보호**: 이 컴퓨터를 추적 대상으로 등록(6자리 페어링), 웹캠 설정

## 실행
    python3 -m venv .venv
    . .venv/bin/activate
    pip install -r requirements.txt
    python main.py

## 구조
- main.py      : GUI (PySide6)
- api.py       : 서버 통신 (JSON API)
- agent_ctl.py : '이 기기 보호' 탭의 에이전트 설치·제어 (리눅스: pkexec)

## 주의
- '이 기기 보호'로 에이전트를 설치하려면, 에이전트 프로그램이
  /usr/local/lib/dorawa 에 먼저 있어야 한다(설치 패키지에 동봉 예정).
  지금은 터미널 install.sh로 깐 상태를 가정.
- 윈도우판 에이전트 제어는 추후 구현.

## 라이선스
MIT © 장현기 (VertigoJang)
