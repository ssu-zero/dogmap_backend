#!/bin/bash
# api.dogmap.store용 Let's Encrypt 인증서 최초 발급 스크립트.
# EC2에서 딱 한 번만 실행하면 된다 (DNS가 이 서버로 전파된 뒤에 실행해야 함 -
# HTTP-01 challenge가 실제로 이 서버에 도달해야 인증서를 발급받을 수 있음).
# 이미 인증서가 있으면 아무것도 하지 않고 종료한다. 이후 갱신은 docker-compose.yml의
# certbot 서비스가 자동으로 처리한다.
set -e

DOMAIN="api.dogmap.store"
EMAIL="jsa020910@gmail.com"
DATA_PATH="./data/certbot"

# renewal 설정 파일은 certbot이 실제 발급에 성공했을 때만 만든다 — 1단계의 더미
# 자체서명 인증서는 이 파일을 만들지 않으므로, 이 파일 존재 여부로 "진짜 인증서 있음"을
# 판단한다 (live/ 디렉토리만 보면 실패한 이전 시도의 빈 디렉토리에 속아 스킵해버림).
if [ -f "$DATA_PATH/conf/renewal/$DOMAIN.conf" ]; then
  echo "이미 $DOMAIN 인증서가 존재합니다. 건너뜁니다."
  exit 0
fi

mkdir -p "$DATA_PATH/conf" "$DATA_PATH/www"

echo "### 1. nginx가 뜰 수 있도록 임시 자체 서명 인증서 생성..."
# 호스트에서 미리 만든 디렉토리가 바인드 마운트 타이밍/권한 문제로 컨테이너에 안 보이는
# 경우가 있어, 컨테이너 안에서 다시 mkdir -p로 확실히 만들고 openssl을 실행한다.
docker run --rm \
  -v "$(pwd)/$DATA_PATH/conf:/etc/letsencrypt" \
  alpine:3.20 sh -c "apk add --no-cache openssl >/dev/null 2>&1 && \
    mkdir -p '/etc/letsencrypt/live/$DOMAIN' && \
    openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
      -keyout '/etc/letsencrypt/live/$DOMAIN/privkey.pem' \
      -out '/etc/letsencrypt/live/$DOMAIN/fullchain.pem' \
      -subj '/CN=localhost'"

echo "### 2. nginx 기동..."
docker compose up -d nginx

echo "### 3. 임시 인증서 삭제..."
rm -rf "$DATA_PATH/conf/live/$DOMAIN" "$DATA_PATH/conf/archive/$DOMAIN" "$DATA_PATH/conf/renewal/$DOMAIN.conf"

echo "### 4. 실제 인증서 발급 요청 (HTTP-01, webroot)..."
docker run --rm \
  -v "$(pwd)/$DATA_PATH/conf:/etc/letsencrypt" \
  -v "$(pwd)/$DATA_PATH/www:/var/www/certbot" \
  certbot/certbot certonly --webroot -w /var/www/certbot \
    --email "$EMAIL" -d "$DOMAIN" \
    --rsa-key-size 4096 --agree-tos --no-eff-email --non-interactive

echo "### 5. nginx 재시작해서 새 인증서 적용..."
docker compose restart nginx

echo "완료: https://$DOMAIN 확인해보세요."
