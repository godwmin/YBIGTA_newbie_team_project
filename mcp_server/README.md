# Crypto Price MCP Server

`coin_prices` 테이블을 읽기 전용으로 조회하는 MCP Server입니다. MCP 표준 Streamable HTTP를 사용하며 기본 엔드포인트는 `http://localhost:8000/mcp`입니다.

## 3계층 구조

- `tools/`: MCP Tool 이름·설명·JSON Schema와 안전한 오류 응답
- `services/`: symbol 정규화, `limit`/`hours` 범위 검증, 응답 모델 변환
- `repositories/`: 파라미터 바인딩된 고정 `SELECT` SQL

Tool이 DB SQL을 직접 모르므로 스키마가 바뀌면 repository만, 비즈니스 규칙이 바뀌면 service만 수정할 수 있습니다.

## MCP Tools

| Tool | 입력 | 제한 | 설명 |
|---|---|---|---|
| `get_latest_price` | `symbol` | `KRW-BTC` 형식 | 특정 코인 최신 시세 |
| `get_top_gainers` | `limit` | 1~20 | 코인별 최신 값 기준 상승률 상위 N개 |
| `get_price_history` | `symbol`, `hours` | 1~168시간, 최대 500행 | 최근 N시간 시세 내역 |

`change_rate`는 Upbit 원본 비율입니다. 예를 들어 `0.0325`는 3.25%이며, 응답에 `change_rate_percent`도 함께 제공합니다.

## 로컬 실행

Python 3.10 이상이 필요합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r mcp_server/requirements-dev.txt
cp .env.example .env
```

`.env`에 `MCP_DB_PASSWORD`, 16자 이상의 `MCP_AUTH_TOKEN`을 입력한 뒤 실행합니다.

```bash
python -m mcp_server.server
```

`GET /health`는 Nginx/EC2 health check용 공개 경로이고, `/mcp`는 반드시 다음 헤더가 필요합니다.

```http
Authorization: Bearer <MCP_AUTH_TOKEN>
```

## DB 적용

RDS 관리자가 순서대로 실행합니다.

1. `database/schema.sql`
2. `database/grants.sql` 내 `CHANGE_ME` 비밀번호를 실행 직전 교체
3. 로컬 테스트에서만 선택적으로 `database/seed.sql`

`mcp_user`는 `SELECT`만, `collector_user`는 `INSERT`만 보유합니다. RDS Security Group도 3306 Inbound source를 EC2의 `mcp-sg`로 제한해야 합니다.

## 테스트와 캡처

```bash
pytest mcp_server/tests
npx -y @modelcontextprotocol/inspector
```

Inspector에서 URL을 `http://localhost:8000/mcp`, Bearer Token을 `.env`의 값으로 설정합니다.

- `mcp_tools.png`: 3개 Tool 목록과 입력 Schema
- `mcp_call.png`: `get_latest_price` 또는 `get_top_gainers` 호출 성공 결과
