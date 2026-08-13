#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 보안 설정 자동 검증 스크립트 (팀원3)
#
# 과제 채점 항목을 하나씩 실제로 확인하고 PASS/FAIL을 출력한다.
# 이 출력을 그대로 캡처하면 README의 보안 설계 설명 근거가 된다.
#
# 사전 준비
#   - AWS CLI v2 설치 + `aws configure` 완료 (읽기 권한만 있으면 충분)
#   - jq 설치
#   - 로컬(노트북)에서 실행할 것. EC2 안에서 돌리면 "외부에서 막히는지"를
#     확인하는 5번 항목이 무의미해진다.
#
# 사용
#   ./verify_security.sh <rds-instance-identifier> <ec2-public-ip> [mcp-sg-name]
# 예시
#   ./verify_security.sh ybigta-agent-rds 3.36.12.34 mcp-sg
# ---------------------------------------------------------------------------
set -uo pipefail

RDS_ID="${1:?사용법: ./verify_security.sh <rds-id> <ec2-public-ip> [mcp-sg-name]}"
EC2_IP="${2:?사용법: ./verify_security.sh <rds-id> <ec2-public-ip> [mcp-sg-name]}"
MCP_SG_NAME="${3:-mcp-sg}"

PASS=0
FAIL=0

ok()   { echo -e "  \033[32mPASS\033[0m  $*"; PASS=$((PASS + 1)); }
bad()  { echo -e "  \033[31mFAIL\033[0m  $*"; FAIL=$((FAIL + 1)); }
info() { echo -e "  ....  $*"; }
section() { echo; echo "=== $* ==="; }

for cmd in aws jq curl; do
  command -v "$cmd" >/dev/null || { echo "$cmd 가 필요합니다."; exit 1; }
done

# ---------------------------------------------------------------------------
section "1. RDS Public Access 비활성화"
# ---------------------------------------------------------------------------
RDS_JSON=$(aws rds describe-db-instances --db-instance-identifier "${RDS_ID}" 2>/dev/null)
if [[ -z "${RDS_JSON}" ]]; then
  bad "RDS '${RDS_ID}' 를 찾을 수 없습니다 (리전/이름 확인)"
else
  PUBLIC=$(echo "${RDS_JSON}" | jq -r '.DBInstances[0].PubliclyAccessible')
  ENDPOINT=$(echo "${RDS_JSON}" | jq -r '.DBInstances[0].Endpoint.Address')
  RDS_SG_ID=$(echo "${RDS_JSON}" | jq -r '.DBInstances[0].VpcSecurityGroups[0].VpcSecurityGroupId')
  RDS_SUBNETS=$(echo "${RDS_JSON}" | jq -r '.DBInstances[0].DBSubnetGroup.Subnets[].SubnetIdentifier')

  [[ "${PUBLIC}" == "false" ]] \
    && ok "PubliclyAccessible = false" \
    || bad "PubliclyAccessible = ${PUBLIC}  <- 반드시 false여야 함"

  info "endpoint = ${ENDPOINT}"
fi

# ---------------------------------------------------------------------------
section "2. RDS가 Private Subnet에 있는가 (IGW 라우트 없음)"
# ---------------------------------------------------------------------------
if [[ -n "${RDS_SUBNETS:-}" ]]; then
  for SUBNET in ${RDS_SUBNETS}; do
    RT=$(aws ec2 describe-route-tables \
          --filters "Name=association.subnet-id,Values=${SUBNET}" \
          --query 'RouteTables[0].Routes[?GatewayId!=`null`].GatewayId' \
          --output text 2>/dev/null)
    # 명시적 연결이 없으면 VPC 메인 라우트 테이블을 따른다
    if [[ -z "${RT}" || "${RT}" == "None" ]]; then
      VPC_ID=$(aws ec2 describe-subnets --subnet-ids "${SUBNET}" \
                --query 'Subnets[0].VpcId' --output text)
      RT=$(aws ec2 describe-route-tables \
            --filters "Name=vpc-id,Values=${VPC_ID}" "Name=association.main,Values=true" \
            --query 'RouteTables[0].Routes[?GatewayId!=`null`].GatewayId' --output text)
      info "${SUBNET}: 명시적 라우트 테이블 없음 -> 메인 라우트 테이블 사용"
    fi

    if echo "${RT}" | grep -q "igw-"; then
      bad "${SUBNET} 가 Internet Gateway로 라우팅됨 -> Public Subnet이다"
    else
      ok "${SUBNET} 에 IGW 라우트 없음 (Private)"
    fi
  done
fi

# ---------------------------------------------------------------------------
section "3. RDS Security Group 인바운드"
# ---------------------------------------------------------------------------
if [[ -n "${RDS_SG_ID:-}" ]]; then
  SG_JSON=$(aws ec2 describe-security-groups --group-ids "${RDS_SG_ID}")
  echo "${SG_JSON}" | jq -r '.SecurityGroups[0].IpPermissions[]
    | "  rule: \(.FromPort // "all")-\(.ToPort // "all")/\(.IpProtocol)  cidr=\([.IpRanges[].CidrIp] | join(","))  sg=\([.UserIdGroupPairs[].GroupId] | join(","))"'

  OPEN_CIDR=$(echo "${SG_JSON}" | jq -r '[.SecurityGroups[0].IpPermissions[].IpRanges[].CidrIp] | index("0.0.0.0/0") // "no"')
  [[ "${OPEN_CIDR}" == "no" ]] \
    && ok "0.0.0.0/0 인바운드 없음" \
    || bad "0.0.0.0/0 인바운드가 존재한다 <- 즉시 제거할 것"

  SRC_SG_COUNT=$(echo "${SG_JSON}" | jq '[.SecurityGroups[0].IpPermissions[].UserIdGroupPairs[]] | length')
  [[ "${SRC_SG_COUNT}" -gt 0 ]] \
    && ok "Source가 Security Group으로 지정되어 있음 (${SRC_SG_COUNT}건)" \
    || bad "Source가 Security Group이 아님 <- mcp-sg를 Source로 지정할 것"
fi

# ---------------------------------------------------------------------------
section "4. MCP EC2 Security Group 인바운드 (내부 포트 노출 여부)"
# ---------------------------------------------------------------------------
MCP_SG_JSON=$(aws ec2 describe-security-groups \
                --filters "Name=group-name,Values=${MCP_SG_NAME}" 2>/dev/null)
if [[ $(echo "${MCP_SG_JSON}" | jq '.SecurityGroups | length') -eq 0 ]]; then
  bad "Security Group '${MCP_SG_NAME}' 를 찾을 수 없음"
else
  echo "${MCP_SG_JSON}" | jq -r '.SecurityGroups[0].IpPermissions[]
    | "  rule: \(.FromPort // "all")-\(.ToPort // "all")/\(.IpProtocol)  cidr=\([.IpRanges[].CidrIp] | join(","))"'

  # 인터넷에 열려 있으면 안 되는 포트들
  for PORT in 8000 3000 5000 9200 3306 5432 27017; do
    EXPOSED=$(echo "${MCP_SG_JSON}" | jq -r --argjson p "${PORT}" '
      [.SecurityGroups[0].IpPermissions[]
       | select((.FromPort // 0) <= $p and (.ToPort // 65535) >= $p)
       | .IpRanges[].CidrIp] | index("0.0.0.0/0") // "no"')
    [[ "${EXPOSED}" == "no" ]] \
      && ok "포트 ${PORT} 인터넷 미공개" \
      || bad "포트 ${PORT} 가 0.0.0.0/0 으로 열려 있다"
  done

  SSH_OPEN=$(echo "${MCP_SG_JSON}" | jq -r '
    [.SecurityGroups[0].IpPermissions[]
     | select((.FromPort // 0) <= 22 and (.ToPort // 65535) >= 22)
     | .IpRanges[].CidrIp] | index("0.0.0.0/0") // "no"')
  [[ "${SSH_OPEN}" == "no" ]] \
    && ok "SSH(22) 가 전체 공개가 아님" \
    || bad "SSH(22) 가 0.0.0.0/0 <- 내 IP/32로 좁힐 것"
fi

# ---------------------------------------------------------------------------
section "5. 실제 외부 접근 테스트 (내 노트북 -> EC2)"
# ---------------------------------------------------------------------------
# MCP 내부 포트: 연결이 안 되는 것이 정상
if curl -s -o /dev/null --connect-timeout 5 "http://${EC2_IP}:8000/" 2>/dev/null; then
  bad "http://${EC2_IP}:8000 에 외부에서 접속됨 <- 내부 포트가 노출되었다"
else
  ok "http://${EC2_IP}:8000 외부 접속 차단됨"
fi

# Nginx(80): 응답이 와야 정상
HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 "http://${EC2_IP}/health" || echo "000")
if [[ "${HTTP_CODE}" == "000" ]]; then
  bad "http://${EC2_IP}/health 응답 없음 (Nginx 또는 MCP 컨테이너 확인)"
else
  ok "Nginx(80) 응답 = HTTP ${HTTP_CODE}"
fi

# 인증 없이 MCP 호출: 401/403 이 나와야 정상
NOAUTH=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 \
          -X POST "http://${EC2_IP}/mcp" \
          -H 'Content-Type: application/json' \
          -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' || echo "000")
case "${NOAUTH}" in
  401|403) ok "인증 없는 MCP 호출 -> HTTP ${NOAUTH} (정상 차단)" ;;
  000)     bad "MCP 엔드포인트 응답 없음 (경로가 /mcp 가 맞는지 팀원1과 확인)" ;;
  200)     bad "인증 없이 HTTP 200 <- Bearer 토큰 검증이 동작하지 않는다" ;;
  *)       info "인증 없는 호출 -> HTTP ${NOAUTH} (팀원1과 기대 응답 확인)" ;;
esac

# ---------------------------------------------------------------------------
section "6. RDS 직접 접속 시도 (외부에서 막혀야 정상)"
# ---------------------------------------------------------------------------
if [[ -n "${ENDPOINT:-}" ]]; then
  if timeout 5 bash -c "cat < /dev/null > /dev/tcp/${ENDPOINT}/3306" 2>/dev/null; then
    bad "외부에서 RDS 3306 에 접속됨 <- Public Access / SG 재확인"
  else
    ok "외부에서 RDS 3306 접속 불가 (DNS 미해석 또는 타임아웃 = 정상)"
  fi
fi

# ---------------------------------------------------------------------------
echo
echo "==========================================="
echo "  PASS: ${PASS}    FAIL: ${FAIL}"
echo "==========================================="
[[ "${FAIL}" -eq 0 ]] || exit 1
