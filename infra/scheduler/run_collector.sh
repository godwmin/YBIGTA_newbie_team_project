#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Collector 실행 래퍼 (cron / systemd timer가 이 스크립트를 호출한다)
#
# 이 래퍼가 필요한 이유
#   1. flock  : 수집이 다음 주기까지 안 끝나도 중복 실행되지 않는다.
#   2. 로깅   : 시작/종료 시각과 종료 코드를 남겨 "자동 갱신 중"임을 증명한다.
#              -> aws/data_update.png 캡처의 근거가 된다.
#   3. 자격증명: collector_user(쓰기 권한) 자격증명을 컨테이너에만 주입한다.
#
# 설치:
#   sudo install -m 755 run_collector.sh /opt/mcp/run_collector.sh
# ---------------------------------------------------------------------------
set -uo pipefail

LOCK_FILE=/var/lock/ybigta-collector.lock
LOG_FILE=/var/log/ybigta/collector.log
ENV_FILE=/opt/mcp/collector.env   # COLLECTOR_IMAGE, DATABASE_URL(collector_user), EXTERNAL_API_KEY ...

log() {
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" | tee -a "${LOG_FILE}"
}

# 이미 돌고 있으면 조용히 종료 (겹쳐 돌면 중복 INSERT가 생긴다)
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  log "SKIP: 이전 수집이 아직 실행 중"
  exit 0
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  log "FAIL: ${ENV_FILE} 없음"
  exit 1
fi

# shellcheck disable=SC1090
set -a; source "${ENV_FILE}"; set +a

: "${COLLECTOR_IMAGE:?COLLECTOR_IMAGE 가 collector.env 에 없습니다}"

START_TS=$(date +%s)
log "START collector image=${COLLECTOR_IMAGE}"

# 수집 프로그램은 MCP 서버와 완전히 분리된 별도 컨테이너로 실행한다.
# --network host 를 쓰지 않는다: RDS는 기본 브리지 네트워크에서도 도달 가능하다.
docker run --rm --name ybigta-collector \
  --env-file "${ENV_FILE}" \
  --memory 512m --cpus 1 \
  "${COLLECTOR_IMAGE}" >>"${LOG_FILE}" 2>&1
EXIT_CODE=$?

ELAPSED=$(( $(date +%s) - START_TS ))

if [[ ${EXIT_CODE} -eq 0 ]]; then
  log "DONE  collector exit=0 elapsed=${ELAPSED}s"
else
  log "FAIL  collector exit=${EXIT_CODE} elapsed=${ELAPSED}s"
fi

exit "${EXIT_CODE}"
