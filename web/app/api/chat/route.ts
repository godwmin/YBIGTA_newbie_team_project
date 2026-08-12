import { NextRequest, NextResponse } from 'next/server';

// MCP 서버 호출 함수 (Next.js 서버에서만 실행되므로 비밀키가 안전함)
async function callMcpTool(toolName: string, args: Record<string, any>) {
  const mcpUrl = process.env.MCP_SERVER_URL || 'http://localhost:8000';
  const mcpToken = process.env.MCP_AUTH_TOKEN || '';

  try {
    const response = await fetch(`${mcpUrl}/tools/${toolName}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${mcpToken}`, // Bearer 토큰 인증
      },
      body: JSON.stringify(args),
    });

    if (!response.ok) {
      throw new Error(`MCP Server Error: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error(`MCP Tool Call Failed (${toolName}):`, error);
    return { error: 'MCP Server 통신 실패' };
  }
}

export async function POST(req: NextRequest) {
  try {
    const { messages } = await req.json();
    const lastUserMessage = messages[messages.length - 1]?.content || '';

    // 1. 단순 예시 라우팅 (실제 LLM Tool Call 또는 규칙 기반 매핑)
    // 질문 분석 후 알맞은 MCP Tool을 호출합니다.
    let mcpResult = null;
    let toolNameCalled = '';

    if (lastUserMessage.includes('최근') || lastUserMessage.includes('가격') || lastUserMessage.includes('시세')) {
      toolNameCalled = 'get_latest_price';
      mcpResult = await callMcpTool('get_latest_price', { symbol: 'KRW-BTC' });
    } else if (lastUserMessage.includes('상승') || lastUserMessage.includes('높은') || lastUserMessage.includes('분석')) {
      toolNameCalled = 'get_top_gainers';
      mcpResult = await callMcpTool('get_top_gainers', { limit: 3 });
    } else {
      toolNameCalled = 'get_price_history';
      mcpResult = await callMcpTool('get_price_history', { symbol: 'KRW-BTC', hours: 24 });
    }

    // 2. MCP에서 가져온 데이터 기반으로 최종 응답 반환
    const aiResponse = `[호출된 MCP Tool: ${toolNameCalled}]\n\n조회 결과 데이터:\n${JSON.stringify(mcpResult, null, 2)}`;

    return NextResponse.json({
      role: 'assistant',
      content: aiResponse,
      toolCalled: toolNameCalled,
    });
  } catch (error) {
    console.error('Chat API Error:', error);
    return NextResponse.json({ error: '서버 에러가 발생했습니다.' }, { status: 500 });
  }
}