#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 과제 종료 후 과금 리소스 점검 (명세의 "주의사항" 대응)
#
# EC2를 Stop해도 RDS / NAT Gateway / EIP / ELB / OpenSearch 는 계속 과금된다.
# 제출 직후 이 스크립트를 돌려서 남은 리소스를 한 번에 확인한다.
#
#   ./cleanup_check.sh              # 조회만 (안전)
#   ./cleanup_check.sh --regions    # 전 리전 훑기 (다른 리전에 만든 걸 놓치기 쉽다)
#
# 이 스크립트는 아무것도 삭제하지 않는다. 삭제는 콘솔에서 직접 할 것.
# ---------------------------------------------------------------------------
set -uo pipefail

REGIONS="${AWS_REGION:-ap-northeast-2}"
if [[ "${1:-}" == "--regions" ]]; then
  REGIONS=$(aws ec2 describe-regions --query 'Regions[].RegionName' --output text)
fi

for R in ${REGIONS}; do
  echo
  echo "############ ${R} ############"

  echo "--- EC2 (running/stopped) ---"
  aws ec2 describe-instances --region "${R}" \
    --filters "Name=instance-state-name,Values=running,stopped" \
    --query 'Reservations[].Instances[].[InstanceId,InstanceType,State.Name,Tags[?Key==`Name`]|[0].Value]' \
    --output table 2>/dev/null || echo "  (조회 실패/권한 없음)"

  echo "--- RDS (Stop해도 7일 후 자동 재시작 + 스토리지 과금) ---"
  aws rds describe-db-instances --region "${R}" \
    --query 'DBInstances[].[DBInstanceIdentifier,DBInstanceClass,DBInstanceStatus,PubliclyAccessible]' \
    --output table 2>/dev/null || echo "  (없음)"

  echo "--- NAT Gateway (시간당 과금. 안 쓰면 즉시 삭제) ---"
  aws ec2 describe-nat-gateways --region "${R}" \
    --filter "Name=state,Values=available,pending" \
    --query 'NatGateways[].[NatGatewayId,State,VpcId]' \
    --output table 2>/dev/null || echo "  (없음)"

  echo "--- Elastic IP (인스턴스에 안 붙어 있으면 과금) ---"
  aws ec2 describe-addresses --region "${R}" \
    --query 'Addresses[].[PublicIp,InstanceId,AllocationId]' \
    --output table 2>/dev/null || echo "  (없음)"

  echo "--- Load Balancer ---"
  aws elbv2 describe-load-balancers --region "${R}" \
    --query 'LoadBalancers[].[LoadBalancerName,Type,State.Code]' \
    --output table 2>/dev/null || echo "  (없음)"

  echo "--- OpenSearch ---"
  aws opensearch list-domain-names --region "${R}" \
    --query 'DomainNames[].DomainName' --output table 2>/dev/null || echo "  (없음)"

  echo "--- EBS 볼륨 (available = 인스턴스에서 분리된 채 과금 중) ---"
  aws ec2 describe-volumes --region "${R}" \
    --filters "Name=status,Values=available" \
    --query 'Volumes[].[VolumeId,Size,State]' \
    --output table 2>/dev/null || echo "  (없음)"
done

echo
echo "정리 순서 권장: EC2 종료 -> RDS 삭제(최종 스냅샷 생략) -> EIP release"
echo "               -> NAT Gateway 삭제 -> available 상태 EBS 삭제 -> VPC 삭제"
echo "Terraform으로 만들었다면:  cd infra/terraform && terraform destroy"
