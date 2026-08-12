'use client';

import { useState } from 'react';
import { Send, Bot, User } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export default function Home() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: '안녕하세요! 가상자산 시세 분석 AI Agent입니다. 궁금하신 종목 시세나 분석 질문을 입력해주세요.',
    },
  ]);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage: Message = { id: Date.now().toString(), role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: [...messages, userMessage] }),
      });

      const data = await res.json();
      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.content || '응답을 받아오지 못했습니다.',
      };
      setMessages((prev) => [...prev, botMessage]);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex flex-col h-screen max-w-4xl mx-auto p-4 bg-gray-50">
      <header className="py-4 border-b mb-4">
        <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
          <Bot className="w-7 h-7 text-blue-600" /> Data Analysis AI Agent
        </h1>
        <p className="text-sm text-gray-500">MCP를 통해 안전하게 DB 데이터를 조회하고 분석합니다.</p>
      </header>

      <div className="flex-1 overflow-y-auto space-y-4 p-4 bg-white rounded-lg shadow-inner">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex items-start gap-3 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}
          >
            <div className={`p-2 rounded-full ${m.role === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}>
              {m.role === 'user' ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
            </div>
            <div className={`p-3 rounded-lg max-w-[80%] whitespace-pre-wrap ${m.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-800'}`}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && <div className="text-gray-400 text-sm">MCP 데이터 조회 및 답변 생성 중...</div>}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2 mt-4">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="예: 비트코인 최근 가격 알려줘 / 상승률 높은 코인 분석해줘"
          className="flex-1 p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-black"
        />
        <button
          type="submit"
          disabled={loading}
          className="px-5 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-1 font-semibold"
        >
          <Send className="w-4 h-4" /> 전송
        </button>
      </form>
    </main>
  );
}