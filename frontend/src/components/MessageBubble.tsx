import { ChatMessage } from "../hooks/useChatStream";

interface Props {
  message: ChatMessage;
  showDebug: boolean;
}

export function MessageBubble({ message, showDebug }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[80%] ${isUser ? "items-end" : "items-start"}`}>
        <div
          className={`whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm shadow-sm ${
            isUser
              ? "bg-sky-600 text-white"
              : "bg-white text-slate-800 border border-slate-200"
          }`}
        >
          {message.content || (
            <span className="inline-flex gap-1 text-slate-400">
              <span className="animate-pulse">●</span>
              <span className="animate-pulse [animation-delay:150ms]">●</span>
              <span className="animate-pulse [animation-delay:300ms]">●</span>
            </span>
          )}
        </div>

        {showDebug && !isUser && message.toolCalls.length > 0 && (
          <div className="mt-2 space-y-2">
            {message.toolCalls.map((tc, i) => (
              <details
                key={i}
                className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900"
              >
                <summary className="cursor-pointer font-mono font-semibold">
                  🔧 {tc.name}({JSON.stringify(tc.arguments)})
                </summary>
                <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all">
                  {JSON.stringify(tc.result, null, 2)}
                </pre>
              </details>
            ))}
          </div>
        )}

        {showDebug && !isUser && message.sources.length > 0 && (
          <div className="mt-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-900">
            <div className="font-semibold">Retrieved sources</div>
            <ul className="mt-1 space-y-1">
              {message.sources.map((s, i) => (
                <li key={i}>
                  <span className="font-medium">{s.title}</span>
                  {s.score != null && (
                    <span className="text-emerald-600"> (score {s.score})</span>
                  )}
                  : {s.snippet}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
