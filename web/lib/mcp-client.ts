import {
  Client,
  StreamableHTTPClientTransport,
  type CallToolResult,
  type Tool as McpTool,
} from '@modelcontextprotocol/client';
import { dynamicTool, jsonSchema, type ToolSet } from 'ai';

function requiredServerEnv(name: 'MCP_SERVER_URL' | 'MCP_AUTH_TOKEN'): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is not configured on the server`);
  return value;
}

export async function createMcpToolSet(): Promise<{
  client: Client;
  tools: ToolSet;
}> {
  const token = requiredServerEnv('MCP_AUTH_TOKEN');
  const configuredTimeout = Number(process.env.MCP_REQUEST_TIMEOUT_MS ?? '15000');
  const timeout = Number.isInteger(configuredTimeout) && configuredTimeout > 0
    ? configuredTimeout
    : 15_000;
  const client = new Client({ name: 'crypto-nextjs-agent', version: '1.0.0' });
  const transport = new StreamableHTTPClientTransport(
    new URL(requiredServerEnv('MCP_SERVER_URL')),
    { authProvider: { token: async () => token } },
  );

  await client.connect(transport, { timeout });
  const { tools: mcpTools } = await client.listTools(undefined, { timeout });

  return {
    client,
    tools: Object.fromEntries(
      mcpTools.map((mcpTool: McpTool) => [
        mcpTool.name,
        dynamicTool({
          description: mcpTool.description,
          inputSchema: jsonSchema(
            mcpTool.inputSchema as Parameters<typeof jsonSchema>[0],
          ),
          execute: async (input): Promise<CallToolResult> => {
            const result = await client.callTool(
              { name: mcpTool.name, arguments: input as Record<string, unknown> },
              { timeout },
            );
            if (result.isError) {
              throw new Error(`MCP tool ${mcpTool.name} returned an error`);
            }
            return result;
          },
        }),
      ]),
    ),
  };
}
