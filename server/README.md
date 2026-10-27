# Dorawa Server

노트북 도난 추적기 Dorawa의 서버. 노트북이 보낸 위치·사진을 받아 저장하고,
사용자가 웹에서 보고 도난 모드를 켠다. 노트북은 6자리 코드로 계정과 짝지어진다.

## 로컬 실행 (테스트)
    python3 -m venv .venv
    . .venv/bin/activate
    pip install -r requirements.txt
    python server/app.py
브라우저에서 http://localhost:8080 → 회원가입 → 페어링 코드 발급.

## 흐름
1. 웹에서 회원가입/로그인
2. "페어링 코드 만들기" → 6자리 코드
3. 노트북 Dorawa 에이전트에서 그 코드 입력 → 기기 전용 키 발급
4. 노트북이 /api/report 로 보고, /api/poll 로 도난 여부 확인
5. 웹에서 "도난 모드 켜기" → 노트북이 다음 poll에서 감지

## 배포 (나중)
- 지금: 클라우드 무료 티어(Oracle 등)에 올림
- 이후: 집 미니 PC + Cloudflare Tunnel 로 이전 (코드는 그대로)
- 운영 시 gunicorn + HTTPS 권장. 1차는 개발 서버로 동작 확인.

## 라이선스
MIT © 장현기 (VertigoJang)
