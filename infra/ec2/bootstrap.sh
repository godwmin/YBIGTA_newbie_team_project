#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# EC2 user_data / 초기 부트스트랩
#
# 하는 일
#   1. Docker 설치            (MCP Server 컨테이너 실행용)
#   2. Nginx 설치 + 리버스 프록시 설정 (80 -> 127.0.0.1:8000)
#   3. MySQL client 설치      (RDS 연결 확인 및 계정 분리 SQL 실행용)
#   4. collector용 로그 디렉토리와 cron 준비
#
# Terraform이 user_data로 자동 실행한다.
# 콘솔로 EC2를 직접 만든 경우에는 SSH 접속 후 다음처럼 수동 실행:
#   sudo bash bootstrap.sh
#
# 로그: /var/log/cloud-init-output.log
# ---------------------------------------------------------------------------
set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive

APP_DIR=/opt/mcp
LOG_DIR=/var/log/ybigta

# ------------------------------ 1. 패키지 ----------------------------------
apt-get update -y
apt-get install -y \
  ca-certificates curl gnupg \
  docker.io \
  nginx \
  mysql-client \
  cron \
  jq

systemctl enable --now docker
systemctl enable --now cron

# ubuntu 유저가 sudo 없이 docker를 쓸 수 있도록
usermod -aG docker ubuntu || true

mkdir -p "${APP_DIR}" "${LOG_DIR}"
chown -R ubuntu:ubuntu "${APP_DIR}" "${LOG_DIR}"

# --------------------------- 2. Nginx 리버스 프록시 -------------------------
# MCP 애플리케이션은 127.0.0.1:8000 에만 바인딩한다.
# 인터넷에서 들어오는 트래픽은 반드시 Nginx(80)를 거친다.
rm -f /etc/nginx/sites-enabled/default

cat >/etc/nginx/conf.d/mcp.conf <<'NGINX'
# MCP Server 리버스 프록시
#   Internet :80  ->  Nginx  ->  127.0.0.1:8000 (MCP, Docker 컨테이너)
#
# 8000번 포트는 Security Group에도 열려 있지 않고,
# 컨테이너도 127.0.0.1 에만 바인딩되어 있으므로 외부에서 직접 접근이 불가능하다.

# 인증 실패/폭주에 대비한 아주 가벼운 rate limit
limit_req_zone $binary_remote_addr zone=mcp_rl:10m rate=20r/s;

server {
    listen 80 default_server;
    server_name _;

    # 서버 버전 노출 방지
    server_tokens off;

    # 업로드 바디 제한 (MCP는 작은 JSON-RPC 요청만 받는다)
    client_max_body_size 1m;

    # 헬스체크는 인증 없이 열어둔다 (토큰 검증 없음, 데이터 없음)
    location = /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }

    location / {
        limit_req zone=mcp_rl burst=40 nodelay;

        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;

        # Authorization 헤더는 그대로 MCP 서버까지 전달되어야 한다.
        # (인증은 Nginx가 아니라 MCP 애플리케이션이 검증한다)
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # MCP Streamable HTTP / SSE 대응
        proxy_set_header Connection        "";
        proxy_buffering off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
NGINX

nginx -t
systemctl enable --now nginx
systemctl reload nginx

# ------------------------- 3. collector 로그 준비 ---------------------------
touch "${LOG_DIR}/collector.log"
chown ubuntu:ubuntu "${LOG_DIR}/collector.log"

cat >/etc/logrotate.d/ybigta-collector <<'LOGROTATE'
/var/log/ybigta/collector.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
LOGROTATE

echo "bootstrap done: docker=$(docker --version), nginx=$(nginx -v 2>&1)"
