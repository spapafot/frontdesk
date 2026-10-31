import { describe, expect, it } from "vitest";

import { formatChatError, type ChatErrorEvent } from "./chat";

describe("formatChatError", () => {
  it("shows safe copy with a shortened support reference", () => {
    const event: ChatErrorEvent = {
      type: "error",
      code: "assistant_unavailable",
      message: "I couldn't complete that response.",
      correlation_id: "abcdef1234567890abcdef1234567890",
    };

    expect(formatChatError(event)).toBe(
      "I couldn't complete that response. Reference: ABCDEF123456.",
    );
  });
});
