import { openai } from '@ai-sdk/openai';
import { generateText, stepCountIs, type ModelMessage } from 'ai';
import { NextResponse } from 'next/server';

import { createMcpToolSet } from '@/lib/mcp-client';

export const runtime = 'nodejs';
export const maxDuration = 60;

type IncomingMessage = { role: 'user' | 'assistant'; content: string };

class InputError extends Error {}

function parseMessages(value: unknown): ModelMessage[] {
  if (!Array.isArray(value)) throw new InputError('messages must be an array');
  const configuredMax = Number(process.env.MAX_CHAT_MESSAGES ?? '20');
  const maxMessages = Number.isInteger(configuredMax) && configuredMax > 0
    ? Math.min(configuredMax, 100)
    : 20;
  if (value.length === 0 || value.length > maxMessages) {
    throw new InputError(`messages must contain 1-${maxMessages} items`);
  }

  return value.map((item): ModelMessage => {
    const message = item as Partial<IncomingMessage>;
    if (
      (message.role !== 'user' && message.role !== 'assistant') ||
      typeof message.content !== 'string' ||
      message.content.trim().length === 0 ||
      message.content.length > 4000
    ) {
      throw new InputError('invalid chat message');
    }
    return { role: message.role, content: message.content.trim() };
  });
}

function publicError(error: unknown): string {
  const message = error instanceof Error ? error.message : '';
  if (message.includes('OPENAI_API_KEY')) return 'OpenAI API Key가 설정되지 않았습니다.';
  if (message.includes('MCP_')) return 'MCP 서버 환경변수 또는 연결 상태를 확인해주세요.';
  return '답변 생성 중 서버 오류가 발생했습니다.';
}

export async function POST(request: Request) {
  let mcpClient: Awaited<ReturnType<typeof createMcpToolSet>>['client'] | undefined;
  try {
    const body = (await request.json()) as { messages?: unknown };
    const messages = parseMessages(body.messages);
    const mcp = await createMcpToolSet();
    mcpClient = mcp.client;

    const result = await generateText({
      model: openai(process.env.OPENAI_MODEL ?? 'gpt-5.4-mini'),
      system:
        '당신은 한국어 가상자산 데이터 분석 Agent입니다. 가격 관련 사실은 반드시 제공된 MCP Tool로 조회하고, 조회 시각과 변동률 단위를 명확히 설명하세요. 데이터에 없는 미래 가격을 단정하거나 투자 권유를 하지 마세요.',
      messages,
      tools: mcp.tools,
      stopWhen: stepCountIs(5),
      timeout: 50_000,
    });

    const toolCalls = result.steps.flatMap((step) =>
      step.toolCalls.map((call) => call.toolName),
    );
    return NextResponse.json({
      role: 'assistant',
      content: result.text || '조회 결과를 바탕으로 답변을 만들지 못했습니다.',
      toolCalls,
    });
  } catch (error) {
    console.error('Chat route failed:', error);
    const status = error instanceof SyntaxError || error instanceof InputError ? 400 : 500;
    return NextResponse.json({ error: publicError(error) }, { status });
  } finally {
    await mcpClient?.close().catch((error) => console.error('MCP close failed:', error));
  }
}
