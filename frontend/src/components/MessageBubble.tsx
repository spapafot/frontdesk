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
          className={`whitespace-pre-wrap break-words rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? "rounded-br-sm bg-sky-600 text-white"
              : "rounded-bl-sm border border-slate-200 bg-white text-slate-800 shadow-sm"
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

        {!isUser && message.productResults && message.productResults.products.length > 0 && (
          <div
            className="mt-2 grid gap-2 sm:grid-cols-2"
            role="region"
            aria-label="Product results"
          >
            {message.productResults.products.map((product) => (
              <article
                key={product.id}
                className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
              >
                {product.image_url && (
                  <img
                    src={product.image_url}
                    alt=""
                    loading="lazy"
                    referrerPolicy="no-referrer"
                    className="h-32 w-full bg-slate-50 object-cover"
                  />
                )}
                <div className="space-y-1.5 p-3">
                  <h3 className="text-sm font-semibold text-slate-900">{product.name}</h3>
                  {product.price && (
                    <p className="text-sm font-semibold text-sky-700">
                      {product.price} {product.currency_code ?? ""}
                    </p>
                  )}
                  {product.attributes.slice(0, 3).map((attribute) => (
                    <p key={attribute.taxonomy ?? attribute.name} className="text-xs text-slate-500">
                      {attribute.name}: {attribute.terms.map((term) => term.name).join(", ")}
                    </p>
                  ))}
                  <p className="text-xs text-slate-500">
                    {product.is_in_stock ? "In stock" : "Out of stock"}
                  </p>
                  <a
                    href={product.product_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex text-xs font-semibold text-sky-700 hover:text-sky-900"
                  >
                    View product
                  </a>
                </div>
              </article>
            ))}
          </div>
        )}

        {!isUser && message.productResults?.has_more && (
          <p className="mt-2 text-xs text-slate-500">Ask “show me more” for the next page.</p>
        )}

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
