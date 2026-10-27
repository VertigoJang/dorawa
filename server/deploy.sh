#!/bin/bash
# Dorawa 서버 배포 스크립트 (Debian/Ubuntu VM, 예: Google Cloud e2-micro)
# 하는 일: 패키지 설치 -> DuckDNS 연결 -> 코드 배치 -> HTTPS 발급 -> 자동 실행 등록
set -e

if [ "$(id -u)" -ne 0 ]; then
  echo "sudo ./deploy.sh 로 실행하세요."
  exit 1
fi

# ---- 입력받기 ----
read -rp "도메인 (예: dorawa.duckdns.org): " DOMAIN
read -rp "DuckDNS 서브도메인 이름만 (예: dorawa): " DUCK_SUB
read -rsp "DuckDNS 토큰: " DUCK_TOKEN; echo
read -rp "HTTPS 인증서용 이메일: " EMAIL

APP_DIR=/opt/dorawa
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[1/7] 패키지 설치"
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip nginx certbot python3-certbot-nginx curl >/dev/null

echo "[2/7] DuckDNS에 현재 IP 등록 + 5분마다 자동 갱신"
mkdir -p /etc/dorawa
cat > /etc/dorawa/duckdns.sh <<EOF
#!/bin/bash
curl -s "https://www.duckdns.org/update?domains=$DUCK_SUB&token=$DUCK_TOKEN&ip=" >/dev/null
EOF
chmod 700 /etc/dorawa/duckdns.sh
/etc/dorawa/duckdns.sh
# cron 등록 (5분마다 IP 갱신)
( crontab -l 2>/dev/null | grep -v duckdns.sh; echo "*/5 * * * * /etc/dorawa/duckdns.sh" ) | crontab -
echo "  DuckDNS 등록 완료. DNS 전파를 잠시 기다립니다..."
sleep 10

echo "[3/7] 앱 코드 배치 -> $APP_DIR"
mkdir -p "$APP_DIR"
cp -r "$SRC_DIR/server" "$APP_DIR"/
cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q Flask gunicorn

echo "[4/7] 앱 비밀키 생성 + systemd 서비스 등록"
SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
# 환경 파일 (SMTP 정보는 나중에 여기에 채운다)
mkdir -p /etc/dorawa
if [ ! -f /etc/dorawa/web.env ]; then
  cat > /etc/dorawa/web.env <<EOF
DORAWA_SECRET_KEY=$SECRET_KEY
DORAWA_DB=$APP_DIR/server/data/dorawa.db
DORAWA_PHOTOS=$APP_DIR/server/data/photos
# 이메일 인증을 쓰려면 아래 두 줄을 채우세요 (Gmail 앱 비밀번호)
DORAWA_SMTP_USER=
DORAWA_SMTP_PASS=
EOF
  chmod 600 /etc/dorawa/web.env
fi
# 롱폴링 때문에 워커 1 + 스레드 다수 (이벤트 메모리 공유 + 동시 대기)
cat > /etc/systemd/system/dorawa-web.service <<EOF
[Unit]
Description=Dorawa web server
After=network.target

[Service]
WorkingDirectory=$APP_DIR/server
EnvironmentFile=/etc/dorawa/web.env
ExecStart=$APP_DIR/.venv/bin/gunicorn -w 1 --threads 16 -b 127.0.0.1:8080 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now dorawa-web.service

echo "[5/7] nginx 리버스 프록시 설정"
cat > /etc/nginx/sites-available/dorawa <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size 50M;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF
ln -sf /etc/nginx/sites-available/dorawa /etc/nginx/sites-enabled/dorawa
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo "[6/7] HTTPS 인증서 발급 (Let's Encrypt)"
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" --redirect

echo "[7/7] 완료"
echo
echo "  서버 주소:  https://$DOMAIN"
echo "  이제 브라우저에서 위 주소로 접속해 회원가입하세요."
echo "  노트북 Dorawa 설정 때 서버 주소에 https://$DOMAIN 을 넣으면 됩니다."
