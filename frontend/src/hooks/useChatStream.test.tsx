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
});
