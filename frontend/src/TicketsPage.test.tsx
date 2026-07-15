import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CallbackTicket, Operator } from "./api/live";
import { TicketsPage } from "./pages/TicketsPage";

const OWNER: Operator = { user_id: "owner-1", email: "owner@acme.com", is_owner: true };
const MEMBER: Operator = { user_id: "member-2", email: "member@acme.com", is_owner: false };

function ticket(over: Partial<CallbackTicket> = {}): CallbackTicket {
  return {
    id: 1,
    conversation_id: 11,
    customer_name: "Vis Itor",
    customer_email: "vis@example.com",
    customer_message: "Please call me back.",
    status: "pending",
    assignee_user_id: null,
    archived: false,
    created_at: "2026-07-14T08:00:00Z",
    resolved_at: null,
    ...over,
  };
}

type Props = Parameters<typeof TicketsPage>[0];

function renderPage(over: Partial<Props> = {}) {
  const props: Props = {
    callbacks: [ticket()],
    operators: [OWNER, MEMBER],
    isOwner: true,
    currentUserId: OWNER.user_id,
    onMove: vi.fn(),
    onAssign: vi.fn(),
    onSetArchived: vi.fn(),
    ...over,
  };
  render(<TicketsPage {...props} />);
  return props;
}

/** Minimal stand-in for the DataTransfer jsdom doesn't implement. */
function makeDataTransfer() {
  const data: Record<string, string> = {};
  return {
    setData: (type: string, value: string) => {
      data[type] = value;
    },
    getData: (type: string) => data[type] ?? "",
    effectAllowed: "",
    dropEffect: "",
  };
}

afterEach(cleanup);

describe("TicketsPage board", () => {
  it("places tickets in their status columns and hides archived ones", () => {
    renderPage({
      callbacks: [
        ticket(),
        ticket({ id: 2, customer_email: "b@x.com", status: "in_progress" }),
        ticket({ id: 3, customer_email: "c@x.com", status: "resolved" }),
        ticket({ id: 4, customer_email: "d@x.com", status: "resolved", archived: true }),
      ],
    });

    expect(within(screen.getByRole("region", { name: "New" })).getByText("vis@example.com")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "In progress" })).getByText("b@x.com")).toBeInTheDocument();
    const resolved = screen.getByRole("region", { name: "Resolved" });
    expect(within(resolved).getByText("c@x.com")).toBeInTheDocument();
    expect(within(resolved).queryByText("d@x.com")).not.toBeInTheDocument();
  });

  it("moves tickets with the fallback buttons", async () => {
    const { onMove } = renderPage({
      callbacks: [
        ticket(),
        ticket({ id: 2, customer_email: "b@x.com", status: "in_progress" }),
        ticket({ id: 3, customer_email: "c@x.com", status: "resolved" }),
      ],
    });

    await userEvent.click(screen.getByRole("button", { name: "Start" }));
    expect(onMove).toHaveBeenCalledWith(1, "in_progress");
    await userEvent.click(screen.getByRole("button", { name: "Resolve" }));
    expect(onMove).toHaveBeenCalledWith(2, "resolved");
    await userEvent.click(screen.getByRole("button", { name: "Reopen" }));
    expect(onMove).toHaveBeenCalledWith(3, "in_progress");
  });

  it("moves a dragged card on drop, ignoring drops on its own column", () => {
    const { onMove } = renderPage();
    const dataTransfer = makeDataTransfer();
    const card = screen.getByText("Vis Itor").closest('[draggable="true"]');
    expect(card).not.toBeNull();

    fireEvent.dragStart(card as Element, { dataTransfer });
    fireEvent.drop(screen.getByRole("region", { name: "New" }), { dataTransfer });
    expect(onMove).not.toHaveBeenCalled();

    fireEvent.drop(screen.getByRole("region", { name: "In progress" }), { dataTransfer });
    expect(onMove).toHaveBeenCalledWith(1, "in_progress");
  });

  it("reassigns through the assignee picker", async () => {
    const { onAssign } = renderPage();

    await userEvent.click(screen.getByRole("button", { name: "Assignee: Unassigned" }));
    expect(screen.getByText("owner@acme.com (you)")).toBeInTheDocument();
    await userEvent.click(screen.getByText("member@acme.com"));

    expect(onAssign).toHaveBeenCalledWith(1, MEMBER.user_id);
  });

  it("shows a static assignee chip for solo accounts", () => {
    renderPage({ operators: [OWNER], callbacks: [ticket({ assignee_user_id: OWNER.user_id })] });

    expect(screen.queryByRole("button", { name: /assignee/i })).not.toBeInTheDocument();
    expect(screen.getByTitle("Assignee")).toHaveTextContent("owner@acme.com");
  });

  it("labels an assignee who left the team", () => {
    renderPage({ callbacks: [ticket({ assignee_user_id: "gone-3" })] });

    expect(screen.getByRole("button", { name: "Assignee: Former member" })).toBeInTheDocument();
  });

  it("lets the owner archive resolved tickets and unarchive from the toggle list", async () => {
    const { onSetArchived } = renderPage({
      callbacks: [
        ticket({ status: "resolved", resolved_at: "2026-07-15T09:00:00Z" }),
        ticket({ id: 2, customer_email: "b@x.com", status: "resolved", archived: true }),
      ],
    });

    await userEvent.click(screen.getByRole("button", { name: "Archive" }));
    expect(onSetArchived).toHaveBeenCalledWith(1, true);

    // Archived tickets live behind the toggle, off the board.
    expect(screen.queryByText("b@x.com")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /archived \(1\)/i }));
    expect(screen.getByText("b@x.com")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Unarchive" }));
    expect(onSetArchived).toHaveBeenCalledWith(2, false);
  });

  it("hides archive controls from team members", async () => {
    renderPage({
      isOwner: false,
      callbacks: [
        ticket({ status: "resolved" }),
        ticket({ id: 2, customer_email: "b@x.com", status: "resolved", archived: true }),
      ],
    });

    expect(screen.queryByRole("button", { name: "Archive" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /archived \(1\)/i }));
    expect(screen.queryByRole("button", { name: "Unarchive" })).not.toBeInTheDocument();
  });
});
