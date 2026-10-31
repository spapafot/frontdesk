import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { LiveConversation } from "./LiveConversation";

const humanState = {
  conversation_id: 11,
  profile_id: 1,
  mode: "human" as const,
  assigned_user_id: "owner-1",
  escalation_requested_at: "2026-07-14T08:00:00Z",
  escalation_expires_at: null,
  accepted_at: "2026-07-14T08:01:00Z",
  closed_at: null,
  messages: [
    {
      id: 1,
      client_message_id: null,
      role: "assistant" as const,
      content: "AI answer",
      sender_type: "ai" as const,
      sender_user_id: null,
      sender_display_name: null,
      created_at: "2026-07-14T07:59:00Z",
    },
    {
      id: 2,
      client_message_id: "operator-1",
      role: "assistant" as const,
      content: "Human answer",
      sender_type: "operator" as const,
      sender_user_id: "owner-1",
      sender_display_name: "Owner",
      created_at: "2026-07-14T08:02:00Z",
    },
  ],
};

describe("LiveConversation", () => {
  it("presents live support as one-way and clearly labels ending it", async () => {
    const user = userEvent.setup();
    const onAction = vi.fn();
    render(<LiveConversation state={humanState} error={null} onAction={onAction} />);

    expect(screen.getByText("Live support active")).toBeInTheDocument();
    expect(screen.getByText(/AI cannot resume/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /return to ai/i })).not.toBeInTheDocument();
    expect(screen.getByText("AI assistant")).toBeInTheDocument();
    expect(screen.getByText("Owner")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "End conversation" }));
    expect(onAction).toHaveBeenCalledWith("close");
  });

  it("labels a closed conversation as ended and keeps the composer disabled", () => {
    const onAction = vi.fn();
    render(
      <LiveConversation
        state={{
          ...humanState,
          mode: "closed",
          closed_at: "2026-07-14T08:10:00Z",
        }}
        error={null}
        onAction={onAction}
      />,
    );

    expect(screen.getByPlaceholderText("This conversation has ended")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(onAction).not.toHaveBeenCalled();
  });

  it("shows the visitor typing indicator and reports the operator's own typing", async () => {
    const user = userEvent.setup();
    const onAction = vi.fn();
    const onTyping = vi.fn();
    render(
      <LiveConversation
        state={humanState}
        error={null}
        onAction={onAction}
        visitorTyping
        onTyping={onTyping}
      />,
    );

    expect(screen.getByRole("status", { name: "Visitor is typing" })).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("Reply to visitor…"), "On it");
    expect(onTyping).toHaveBeenLastCalledWith(true);

    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(onAction).toHaveBeenCalledWith(
      "message",
      expect.objectContaining({ content: "On it" }),
    );
    expect(onTyping).toHaveBeenLastCalledWith(false);
  });

  it("hides the typing indicator when the visitor is not typing", () => {
    render(<LiveConversation state={humanState} error={null} onAction={vi.fn()} />);
    expect(screen.queryByRole("status", { name: "Visitor is typing" })).not.toBeInTheDocument();
  });

  it("keeps the view pinned to the newest message and the typing dots", () => {
    const scrollIntoView = vi
      .spyOn(Element.prototype, "scrollIntoView")
      .mockImplementation(() => {});
    const { rerender } = render(
      <LiveConversation state={humanState} error={null} onAction={vi.fn()} />,
    );
    expect(scrollIntoView).toHaveBeenCalledTimes(1);

    rerender(
      <LiveConversation
        state={{
          ...humanState,
          messages: [
            ...humanState.messages,
            {
              id: 3,
              client_message_id: null,
              role: "user" as const,
              content: "One more thing",
              sender_type: "visitor" as const,
              sender_user_id: null,
              sender_display_name: null,
              created_at: "2026-07-14T08:03:00Z",
            },
          ],
        }}
        error={null}
        onAction={vi.fn()}
      />,
    );
    expect(scrollIntoView).toHaveBeenCalledTimes(2);

    rerender(
      <LiveConversation state={humanState} error={null} onAction={vi.fn()} visitorTyping />,
    );
    expect(scrollIntoView).toHaveBeenCalledTimes(3);
    scrollIntoView.mockRestore();
  });
});
