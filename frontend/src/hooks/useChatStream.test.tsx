import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { streamChat } from "../api/chat";
import { useChatStream } from "./useChatStream";

vi.mock("../api/chat", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/chat")>();
  return { ...actual, streamChat: vi.fn() };
});

describe("useChatStream sensitive input handling", () => {
  beforeEach(() => {
    vi.mocked(streamChat).mockReset();
  });

  it("removes the optimistic raw user message and shows only safe warning copy", async () => {
    vi.mocked(streamChat).mockImplementation(async (_request, onEvent) => {
      onEvent({
        type: "input_blocked",
        code: "sensitive_data_detected",
        message: "Sensitive information was not sent or saved.",
      });
    });
    const onConversationCreated = vi.fn();
    const { result } = renderHook(() =>
      useChatStream({ siteId: 7, onConversationCreated })
    );

    await act(async () => {
      await result.current.send("password=hunter2");
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]).toMatchObject({
      role: "assistant",
      content: "⚠️ Sensitive information was not sent or saved.",
    });
    expect(JSON.stringify(result.current.messages)).not.toContain("hunter2");
    expect(onConversationCreated).not.toHaveBeenCalled();
    expect(result.current.isStreaming).toBe(false);
  });

  it("attaches streamed product results to the assistant message", async () => {
    vi.mocked(streamChat).mockImplementation(async (_request, onEvent) => {
      onEvent({
        type: "product_results",
        page: 1,
        has_more: false,
        products: [
          {
            id: 21,
            name: "Blue Dress",
            slug: "blue-dress",
            summary: "",
            price: "25.99",
            regular_price: "29.99",
            sale_price: "25.99",
            currency_code: "EUR",
            currency_symbol: "€",
            on_sale: true,
            is_in_stock: true,
            has_options: true,
            image_url: null,
            product_url: "https://shop.example/product/blue-dress/",
            attributes: [],
          },
        ],
      });
      onEvent({ type: "token", content: "I found one." });
    });
    const { result } = renderHook(() => useChatStream({ siteId: 7 }));

    await act(async () => {
      await result.current.send("medium dresses");
    });

    expect(result.current.messages[1]).toMatchObject({
      role: "assistant",
      content: "I found one.",
      productResults: {
        page: 1,
        has_more: false,
        products: [{ id: 21, name: "Blue Dress" }],
      },
    });
  });
});
