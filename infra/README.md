# 팀원3 실행 가이드 — AWS 인프라 구축 & 배포

내가(팀원3) 손으로 해야 하는 일만 순서대로 정리했다.
코드/설정은 이미 이 폴더에 다 있으므로, 아래는 **실행과 확인**만 다룬다.

**총 예상 시간: 2~3시간** (RDS 생성 대기 10~15분 포함)

---

## 0. 시작 전 5분 — 팀원들과 먼저 맞출 것

인프라를 만들기 전에 정해져야 뒤에서 되돌아오지 않는다. (2026-08-13 팀 합의 반영)

| 항목 | 누구와 | 확정값 |
|---|---|---|
| **DB 이름** | 팀원2 제안 | ✅ `crypto_db` — 모든 인프라 파일에 반영 완료 |
| **테이블 / 컬럼** | 팀원2 제안 | ✅ `coin_prices` (id, symbol, price, change_rate, collected_at, created_at) |
| **데이터 소스** | 팀원2 제안 | ✅ 업비트 공개 API (API Key 불필요 → `EXTERNAL_API_KEY` 삭제됨) |
| **MCP 서버가 듣는 포트 · 경로** | 팀원1 | 기본 가정 `8000`. **컨테이너는 반드시 `127.0.0.1:8000`에 바인딩** |
| **Collector Docker 이미지 이름** | 팀원2 | ⬜ 미정 — cron이 실행할 이미지 이름 필요 |

내가 팀원들에게 **넘겨줘야 하는 값** (인프라 구축 후):

| 값 | 받는 사람 | 예시 |
|---|---|---|
| RDS 엔드포인트 | 팀원1, 팀원2 | `ybigta-agent-rds.xxxx.ap-northeast-2.rds.amazonaws.com` |
| `mcp_user` 비밀번호 | 팀원1 | MCP의 `MCP_DB_PASSWORD`에 사용 |
| `collector_user` 비밀번호 | 팀원2 | Collector의 `COLLECTOR_DB_PASSWORD`에 사용 |
| EC2 공인 IP | 팀원2 | Vercel의 `MCP_SERVER_URL=http://<IP>` |
| `MCP_AUTH_TOKEN` | 팀원1, 팀원2 | 내가 `openssl rand -hex 32`로 생성해 배포 |

> 비밀번호는 Slack/카톡 평문 대신 1회용 링크나 DM으로 전달하고, 과제 종료 후 리소스와 함께 폐기한다.

---

## 1. 사전 준비 (10분)

```bash
# AWS CLI 설치 확인 및 자격증명 설정
aws --version
aws configure          # Access Key / Secret / region=ap-northeast-2 / json

# 잘 붙었는지 확인
aws sts get-caller-identity

# 내 공인 IP 확인 (SSH 허용에 쓴다)
curl -s https://checkip.amazonaws.com
```

EC2 Key Pair가 없다면 먼저 만든다.

```bash
aws ec2 create-key-pair --key-name ybigta-key \
  --query 'KeyMaterial' --output text > ~/.ssh/ybigta-key.pem
chmod 400 ~/.ssh/ybigta-key.pem
```

---

## 2. 인프라 생성 — 경로 A(Terraform, 권장) 또는 경로 B(콘솔)

### 경로 A. Terraform (약 20분, "멋져요!" 항목 1개 획득)

콘솔에서 20번 클릭할 것을 한 번에 만든다. 정리도 `destroy` 한 줄이다.

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars`를 열어 4개를 채운다.

```hcl
my_ip_cidr         = "<위에서 확인한 IP>/32"
ec2_key_name       = "ybigta-key"
db_master_password = "<강한 비밀번호>"
```

```bash
terraform init
terraform plan       # 생성될 리소스 확인 (RDS publicly_accessible = false 인지 눈으로 보기)
terraform apply      # yes 입력. RDS 때문에 10~15분 걸린다.
```

완료되면 출력값을 메모한다.

```bash
terraform output
terraform output -raw ec2_public_ip
terraform output -raw rds_endpoint
```

> **주의**: `terraform.tfvars`와 `terraform.tfstate`에는 DB 비밀번호가 평문으로 들어간다.
> 이미 `.gitignore`에 넣어뒀지만, 커밋 전 `git status`로 한 번 더 확인할 것.

### 경로 B. AWS 콘솔 (약 50분)

Terraform이 부담스러우면 이대로 클릭한다. 리전은 전부 **서울(ap-northeast-2)**.

<details>
<summary><b>B-1. VPC 만들기</b></summary>

VPC 콘솔 → **VPC 생성** → **VPC 등** 선택 (한 번에 서브넷/라우트까지 생성됨)

- 이름 태그: `ybigta-agent`
- IPv4 CIDR: `10.0.0.0/16`
- 가용 영역 수: **2**
- 퍼블릭 서브넷 수: **2**
- 프라이빗 서브넷 수: **2**
- **NAT 게이트웨이: 없음** ← 반드시 "없음". 시간당 과금된다.
- VPC 엔드포인트: 없음

생성 후 서브넷 이름을 알아보기 쉽게 바꿔둔다 (`...-public-2a`, `...-private-2a` 등).

**확인**: 프라이빗 서브넷의 라우팅 테이블에 `0.0.0.0/0` 항목이 **없어야** 한다.
있으면 Private이 아니다.
</details>

<details>
<summary><b>B-2. Security Group 2개 만들기</b></summary>

EC2 콘솔 → 보안 그룹 → **보안 그룹 생성**

**① `mcp-sg`** (VPC: 방금 만든 것)

| Type | Port | Source | 비고 |
|---|---|---|---|
| HTTP | 80 | `0.0.0.0/0` | Nginx |
| HTTPS | 443 | `0.0.0.0/0` | (TLS 붙일 경우) |
| SSH | 22 | **My IP** | 절대 `0.0.0.0/0` 금지 |

→ **8000번은 추가하지 않는다.** 이게 이 과제 보안 채점의 핵심이다.

**② `rds-sg`** (VPC: 같은 것)

| Type | Port | Source |
|---|---|---|
| MYSQL/Aurora | 3306 | **`mcp-sg`** ← 검색창에 sg 이름을 쳐서 선택 |

Source를 IP가 아니라 **보안 그룹**으로 고르는 것이 포인트다.
</details>

<details>
<summary><b>B-3. RDS 만들기</b></summary>

RDS 콘솔 → **데이터베이스 생성**

- 생성 방식: 표준 생성
- 엔진: **MySQL 8.0**
- 템플릿: **프리 티어**
- DB 인스턴스 식별자: `ybigta-agent-rds`
- 마스터 사용자: `admin` / 비밀번호 설정
- 인스턴스: `db.t3.micro` / 스토리지 20GB gp3

**연결 (가장 중요한 화면)**

- VPC: `ybigta-agent`
- DB 서브넷 그룹: 새로 생성 → **프라이빗 서브넷 2개** 선택
- **퍼블릭 액세스: 아니요(No)** ← 채점 항목
- VPC 보안 그룹: **기존 항목 선택 → `rds-sg`** (default 해제)
- 가용 영역: 아무거나

**추가 구성**

- 초기 데이터베이스 이름: `crypto_db` ← 안 적으면 DB가 안 만들어진다
- 자동 백업: 비활성화 (과제용, 비용 절감)
- 삭제 방지: 비활성화 (나중에 지워야 함)

생성에 10~15분 걸린다. 그동안 B-4를 진행한다.
</details>

<details>
<summary><b>B-4. EC2 만들기</b></summary>

EC2 콘솔 → **인스턴스 시작**

- 이름: `ybigta-agent-mcp-ec2`
- AMI: **Ubuntu Server 24.04 LTS**
- 인스턴스 유형: `t3.micro`
- 키 페어: `ybigta-key`
- 네트워크 설정 → **편집**
  - VPC: `ybigta-agent`
  - 서브넷: **퍼블릭 서브넷** 중 하나
  - 퍼블릭 IP 자동 할당: **활성화**
  - 방화벽: **기존 보안 그룹 선택 → `mcp-sg`**
- 스토리지: 20GB gp3
- **고급 세부 정보 → 사용자 데이터**: `infra/ec2/bootstrap.sh` 내용을 통째로 붙여넣기

사용자 데이터를 넣으면 부팅하면서 Docker · Nginx · cron · MySQL 클라이언트가
자동 설치되고 리버스 프록시까지 설정된다.
</details>

---

## 3. EC2 접속 후 확인 (10분)

```bash
ssh -i ~/.ssh/ybigta-key.pem ubuntu@<EC2_PUBLIC_IP>

# bootstrap이 잘 돌았는지
sudo tail -50 /var/log/cloud-init-output.log
docker --version && systemctl is-active nginx && systemctl is-active cron
```

`bootstrap.sh`를 user_data에 안 넣었다면 지금 수동 실행한다.

```bash
# 로컬에서 파일 전송
scp -i ~/.ssh/ybigta-key.pem infra/ec2/bootstrap.sh ubuntu@<EC2_IP>:/tmp/
# EC2에서
sudo bash /tmp/bootstrap.sh
```

### RDS 연결 확인 — 여기가 첫 관문

```bash
mysql -h <RDS_ENDPOINT> -u admin -p
```

붙으면 성공. **로컬 노트북에서 같은 명령을 실행하면 반드시 실패해야 한다.**
(실패 = Private Subnet 설정이 제대로 된 것)

---

## 4. DB 계정 분리 (15분) — 보안 채점 항목

팀원1의 테이블이 이미 만들어진 뒤에 실행하는 것이 깔끔하다. 아직이면 계정만 먼저 만들어도 된다.

```bash
# 로컬에서 SQL 파일 전송
scp -i ~/.ssh/ybigta-key.pem infra/sql/*.sql ubuntu@<EC2_IP>:/tmp/
```

EC2에서 `01_db_users.sql`을 열어 **3곳을 수정**한다.

- (DB 이름 `crypto_db`는 팀 합의값으로 이미 반영됨)
- `CHANGE_ME_collector_password` → 실제 비밀번호
- `CHANGE_ME_mcp_password` → 실제 비밀번호

```bash
mysql -h <RDS_ENDPOINT> -u admin -p < /tmp/00_schema.sql   # 테이블 먼저
mysql -h <RDS_ENDPOINT> -u admin -p < /tmp/01_db_users.sql
```

### read-only 증명 (이 출력을 캡처할 것)

```bash
mysql --force -h <RDS_ENDPOINT> -u mcp_user -p crypto_db < /tmp/02_verify_readonly.sql
```

`SELECT`는 되고 `INSERT`/`UPDATE`/`DELETE`/`DROP`은 전부
`ERROR 1142 (42000): INSERT command denied to user 'mcp_user'@'...'` 로 떨어지면 통과.

---

## 5. MCP Server 배포 (20분)

팀원1이 Docker 이미지를 푸시한 뒤 진행한다.

```bash
# EC2에서
sudo mkdir -p /opt/mcp

# 실행할 이미지 지정
sudo tee /opt/mcp/image.env >/dev/null <<'EOF'
MCP_IMAGE=<도커허브계정>/ybigta-mcp:latest
EOF

# 비밀값 (mcp_user = read-only 계정을 쓴다)
sudo tee /opt/mcp/.env >/dev/null <<'EOF'
DB_HOST=<RDS_ENDPOINT>
DB_NAME=crypto_db
MCP_DB_USER=mcp_user
MCP_DB_PASSWORD=<PW>
MCP_AUTH_TOKEN=<openssl rand -hex 32 결과>
EOF

sudo chmod 600 /opt/mcp/.env /opt/mcp/image.env

# systemd 서비스 등록
sudo cp /tmp/mcp-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mcp-server
sudo systemctl status mcp-server
```

동작 확인:

```bash
# EC2 내부에서 (직접 8000)
curl -s http://127.0.0.1:8000/health

# EC2 내부에서 (Nginx 경유)
curl -s http://127.0.0.1/health

# 로컬 노트북에서 — 이게 핵심
curl -m 5 http://<EC2_IP>:8000/health   # 반드시 타임아웃 (차단됨)
curl -m 5 http://<EC2_IP>/health        # 정상 응답
```

---

## 6. 자동 수집 스케줄러 등록 (15분)

팀원2가 Collector Docker 이미지를 푸시한 뒤 진행한다.

```bash
# 실행 래퍼 설치
sudo install -m 755 /tmp/run_collector.sh /opt/mcp/run_collector.sh

# Collector 비밀값 (collector_user = 쓰기 계정)
sudo tee /opt/mcp/collector.env >/dev/null <<'EOF'
COLLECTOR_IMAGE=<도커허브계정>/ybigta-collector:latest
DB_HOST=<RDS_ENDPOINT>
DB_NAME=crypto_db
COLLECTOR_DB_USER=collector_user
COLLECTOR_DB_PASSWORD=<PW>
# 업비트 공개 API는 인증 불필요 → API Key 없음
EOF
sudo chmod 600 /opt/mcp/collector.env
sudo chown ubuntu:ubuntu /opt/mcp/collector.env

# 먼저 수동으로 1회 실행해서 동작을 확인한다 (cron에 걸기 전에)
/opt/mcp/run_collector.sh
tail -30 /var/log/ybigta/collector.log

# 잘 돌면 cron 등록
crontab -e     # infra/scheduler/crontab.example 내용 붙여넣기
crontab -l     # 등록 확인
```

### 자동 갱신 증명 — 최소 2주기를 기다려야 한다

30분 간격이면 **1시간 정도 여유를 두고** 아래를 확인한다.
시간이 없으면 주기를 `*/5 * * * *`(5분)로 낮춰 증거를 만든 뒤 되돌려도 된다.

```sql
-- 서로 다른 시각에 수집된 것이 보여야 한다 → data_update.png
SELECT collected_at, COUNT(*) AS rows_collected
FROM <테이블명>
GROUP BY collected_at
ORDER BY collected_at DESC
LIMIT 10;
```

```bash
# 로그로도 증명 가능
grep -E "START|DONE" /var/log/ybigta/collector.log | tail -20
```

---

## 7. 보안 검증 자동 실행 (5분)

**로컬 노트북에서** 실행한다. (EC2 안에서 돌리면 외부 차단 검증이 무의미해진다)

```bash
chmod +x infra/scripts/verify_security.sh
./infra/scripts/verify_security.sh ybigta-agent-rds <EC2_PUBLIC_IP> mcp-sg
```

6개 항목이 전부 PASS여야 한다. FAIL이 있으면 해당 항목의 설정을 고친 뒤 다시 돌린다.
**이 출력 화면도 캡처해두면 README의 보안 설명 근거로 쓸 수 있다.**

---

## 8. 캡처 (10분)

내 담당 필수 캡처 2장. `aws/` 폴더에 정확한 파일명으로 저장한다.

### `aws/rds_private.png`

RDS 콘솔 → `ybigta-agent-rds` → **연결 & 보안** 탭.
한 화면에 아래가 같이 보이게 찍는다.

- **퍼블릭 액세스: 아니요**
- VPC / 서브넷 그룹 (프라이빗 서브넷 2개)
- VPC 보안 그룹: `rds-sg`

### `aws/security_group.png`

EC2 콘솔 → 보안 그룹 → `rds-sg` → **인바운드 규칙** 탭.

- 3306 / 소스가 **`sg-xxxxx (mcp-sg)`** 로 보이는 화면

> 소스 칸에 `0.0.0.0/0`이 아니라 sg 이름이 뜨는 것이 핵심이다.
> `mcp-sg`의 인바운드(8000 없음, SSH가 내 IP)도 같이 찍어 한 장에 넣거나
> 두 번째 파일로 추가하면 설명이 훨씬 강해진다.

### 있으면 좋은 추가 증빙

| 파일 | 내용 |
|---|---|
| `aws/readonly_denied.png` | `02_verify_readonly.sql` 실행 결과 (ERROR 1142) |
| `aws/port_blocked.png` | 로컬에서 `curl :8000` 타임아웃 + `curl :80` 성공 나란히 |
| `aws/cron_registered.png` | `crontab -l` + `tail collector.log` |

---

## 9. README 병합 (10분)

`docs/ARCHITECTURE.md`의 내용을 최종 `README.md`에 붙인다.

- **Architecture** 절 ← `ARCHITECTURE.md` 1번 (다이어그램)
- **Security** 절 ← `ARCHITECTURE.md` 3번 (질문 6개 답변)
- **VPC 구조** ← `ARCHITECTURE.md` 2번
- 캡처 이미지를 `![](aws/rds_private.png)` 형태로 해당 위치에 삽입

팀원1은 MCP Tool 구조를, 팀원2는 Data Pipeline / Agent 사용 예시를 각자 이어 붙인다.

---

## 10. 제출 후 — 반드시 할 것 (5분)

명세에 명시된 항목이다. EC2를 Stop해도 RDS와 EIP는 계속 과금된다.

```bash
./infra/scripts/cleanup_check.sh            # 서울 리전
./infra/scripts/cleanup_check.sh --regions  # 전 리전 (다른 리전 생성분 누락 방지)
```

**단, 채점이 끝나기 전에 지우면 안 된다.** 제출 → 채점 확인 후 정리한다.

```bash
cd infra/terraform && terraform destroy     # Terraform으로 만든 경우
```

콘솔로 만들었다면 순서: EC2 종료 → RDS 삭제(최종 스냅샷 생략) → EIP 릴리스 →
NAT Gateway(있다면) 삭제 → `available` 상태 EBS 삭제 → VPC 삭제.

---

## 자주 나는 문제

| 증상 | 원인과 해결 |
|---|---|
| EC2에서 RDS 접속 타임아웃 | `rds-sg` 인바운드 Source가 `mcp-sg`인지, EC2에 `mcp-sg`가 실제로 붙어 있는지 확인 |
| RDS 엔드포인트가 로컬에서 resolve됨 | 정상. resolve는 되어도 **접속은 안 되면** 통과다 |
| `curl :80` 이 502 Bad Gateway | Nginx는 살아있는데 MCP 컨테이너가 죽었다. `systemctl status mcp-server`, `docker logs mcp-server` |
| `curl :8000` 이 외부에서 열림 | `docker run -p 8000:8000` 으로 떴다. `-p 127.0.0.1:8000:8000` 으로 고칠 것 |
| cron이 안 돈다 | cron은 로그인 셸이 아니라 PATH가 없다. `crontab.example`의 `PATH=` 줄을 반드시 포함 |
| cron에서 `docker: permission denied` | `usermod -aG docker ubuntu` 후 **재로그인** 필요 |
| RDS 생성 시 서브넷 그룹 선택 불가 | 서브넷 그룹에 AZ가 2개 이상 포함돼야 한다 |
| `terraform apply` 가 my_ip_cidr 에러 | `0.0.0.0/0`을 넣었다. `<내IP>/32` 로 바꿀 것 (의도적 방어장치) |
