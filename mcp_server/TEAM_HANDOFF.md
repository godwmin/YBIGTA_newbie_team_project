# 팀 연동 체크리스트

## 팀원 2: Next.js / Collector / Docker

- `MCP_SERVER_URL`은 `/mcp`까지 포함한 전체 엔드포인트입니다.
- MCP는 일반 REST `POST /tools/{name}`가 아닙니다. Next.js server-side Route Handler에서 MCP Streamable HTTP Client로 `tools/list`, `tools/call`을 사용해야 합니다.
- 모든 MCP 요청에 `Authorization: Bearer <MCP_AUTH_TOKEN>`을 추가합니다.
- `MCP_AUTH_TOKEN`, `OPENAI_API_KEY`는 Route Handler 서버에서만 읽고 `NEXT_PUBLIC_`을 붙이지 않습니다.
- Collector와 MCP Server/EC2의 timezone을 UTC로 통일해주세요. `coin_prices` 타임스탬프는 timezone 정보가 없는 MySQL `DATETIME`입니다.
- MCP 실행용 컨테이너가 필요하면 `python -m mcp_server.server`를 entrypoint로 사용합니다.

## 팀원 3: RDS / EC2 / Nginx

- RDS MySQL 8에서 `database/schema.sql` 후 `database/grants.sql`을 관리자 계정으로 적용합니다.
- `grants.sql`의 `CHANGE_ME` 비밀번호는 실행 직전에만 교체하고 Git에 올리지 않습니다.
- `mcp_user`의 `SHOW GRANTS`에 `SELECT ON crypto_db.coin_prices`만 보이는지 확인합니다.
- EC2 내부에서 MCP Server는 `8000`으로 실행하고, 외부에는 Nginx `80/443`만 열어 `/mcp`로 proxy합니다.
- RDS 3306 Inbound source는 EC2에 붙은 `mcp-sg`로만 제한합니다.
- Nginx/EC2 health check은 인증이 필요 없는 `GET /health`를 사용합니다.
