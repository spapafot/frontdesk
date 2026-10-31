import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// The page composes context hooks (auth, site, plan) and the supabase client;
// all four are mocked so each test controls them directly.
const h = vi.hoisted(() => ({
  supabase: {
    auth: {
      signInWithPassword: vi.fn(),
      updateUser: vi.fn(),
      signOut: vi.fn(),
      mfa: {
        listFactors: vi.fn(),
        enroll: vi.fn(),
        challenge: vi.fn(),
        verify: vi.fn(),
        unenroll: vi.fn(),
      },
    },
  },
  site: { ownsAnySite: true },
  plan: {
    billing: undefined as unknown,
    plan: "pro",
    status: "active",
    isLoading: false,
  },
}));

vi.mock("../lib/supabase", () => ({ authEnabled: true, supabase: h.supabase }));
vi.mock("../components/AuthGate", () => ({
  useAuth: () => ({
    canSignOut: true,
    signOut: vi.fn(),
    userId: "user-1",
    userEmail: "admin@example.com",
    isSuperAdmin: false,
  }),
}));
vi.mock("../components/SiteProvider", () => ({ useSite: () => h.site }));
vi.mock("../components/PlanProvider", () => ({ usePlan: () => h.plan }));

import { AccountPage } from "./AccountPage";

const VERIFIED_TOTP = {
  id: "factor-1",
  factor_type: "totp",
  status: "verified",
  friendly_name: "Authenticator app",
  created_at: "2026-07-01T00:00:00Z",
};

function renderPage() {
  return render(
    <MemoryRouter>
      <AccountPage />
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  h.site.ownsAnySite = true;
  h.plan.billing = {
    usage: { messages_used: 100, messages_limit: 5000, bonus_messages: 0, resets_at: null },
    trial_ends_at: null,
    current_period_end: "2026-08-01T00:00:00Z",
  };
  h.plan.plan = "pro";
  h.plan.status = "active";
  h.plan.isLoading = false;
  h.supabase.auth.signInWithPassword.mockResolvedValue({ error: null });
  h.supabase.auth.updateUser.mockResolvedValue({ error: null });
  h.supabase.auth.signOut.mockResolvedValue({ error: null });
  h.supabase.auth.mfa.listFactors.mockResolvedValue({
    data: { all: [], totp: [] },
    error: null,
  });
  h.supabase.auth.mfa.enroll.mockResolvedValue({
    data: {
      id: "factor-1",
      totp: { qr_code: "data:image/svg+xml;utf8,<svg/>", secret: "SECRET123" },
    },
    error: null,
  });
  h.supabase.auth.mfa.challenge.mockResolvedValue({
    data: { id: "challenge-1" },
    error: null,
  });
  h.supabase.auth.mfa.verify.mockResolvedValue({ data: {}, error: null });
  h.supabase.auth.mfa.unenroll.mockResolvedValue({ data: {}, error: null });
});

afterEach(() => {
  cleanup();
});

describe("AccountPage", () => {
  it("shows the signed-in email", async () => {
    renderPage();
    expect(await screen.findByText("admin@example.com")).toBeInTheDocument();
  });

  it("verifies the current password before updating to the new one", async () => {
    renderPage();

    fireEvent.change(screen.getByLabelText(/current password/i), {
      target: { value: "old-secret" },
    });
    fireEvent.change(screen.getByLabelText(/^new password/i), {
      target: { value: "new-secret-1" },
    });
    fireEvent.change(screen.getByLabelText(/confirm new password/i), {
      target: { value: "new-secret-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));

    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    expect(h.supabase.auth.signInWithPassword).toHaveBeenCalledWith({
      email: "admin@example.com",
      password: "old-secret",
    });
    expect(h.supabase.auth.updateUser).toHaveBeenCalledWith({
      password: "new-secret-1",
    });
    expect(
      h.supabase.auth.signInWithPassword.mock.invocationCallOrder[0]
    ).toBeLessThan(h.supabase.auth.updateUser.mock.invocationCallOrder[0]);
  });

  it("stops with an error when the current password is wrong", async () => {
    h.supabase.auth.signInWithPassword.mockResolvedValue({
      error: { message: "Invalid login credentials" },
    });
    renderPage();

    fireEvent.change(screen.getByLabelText(/current password/i), {
      target: { value: "wrong" },
    });
    fireEvent.change(screen.getByLabelText(/^new password/i), {
      target: { value: "new-secret-1" },
    });
    fireEvent.change(screen.getByLabelText(/confirm new password/i), {
      target: { value: "new-secret-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));

    expect(
      await screen.findByText(/current password is incorrect/i)
    ).toBeInTheDocument();
    expect(h.supabase.auth.updateUser).not.toHaveBeenCalled();
  });

  it("shows the plan card with status badge for owners", async () => {
    renderPage();
    expect(await screen.findByText("Pro plan")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /manage billing/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/messages this month/i)).toBeInTheDocument();
  });

  it("tells members that billing belongs to the account owner", async () => {
    h.site.ownsAnySite = false;
    renderPage();
    expect(
      await screen.findByText(/managed by your account owner/i)
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /manage billing/i })
    ).not.toBeInTheDocument();
  });

  it("signs out other sessions only after confirmation", async () => {
    renderPage();

    fireEvent.click(
      screen.getByRole("button", { name: /sign out everywhere else/i })
    );
    expect(h.supabase.auth.signOut).not.toHaveBeenCalled();

    fireEvent.click(
      await screen.findByRole("button", { name: /^sign out others$/i })
    );

    expect(
      await screen.findByText(/signed out on other devices/i)
    ).toBeInTheDocument();
    expect(h.supabase.auth.signOut).toHaveBeenCalledWith({ scope: "others" });
  });

  it("walks through TOTP enrollment: QR + secret, then challenge and verify", async () => {
    renderPage();

    fireEvent.click(
      await screen.findByRole("button", { name: /add authenticator app/i })
    );

    expect(
      await screen.findByAltText(/qr code for your authenticator app/i)
    ).toBeInTheDocument();
    expect(screen.getByText("SECRET123")).toBeInTheDocument();
    expect(h.supabase.auth.mfa.enroll).toHaveBeenCalledWith({
      factorType: "totp",
      friendlyName: "Authenticator app",
    });

    fireEvent.change(screen.getByLabelText(/verification code/i), {
      target: { value: "123456" },
    });
    fireEvent.click(screen.getByRole("button", { name: /turn on two-factor/i }));

    expect(h.supabase.auth.mfa.challenge).toHaveBeenCalledWith({
      factorId: "factor-1",
    });
    await vi.waitFor(() =>
      expect(h.supabase.auth.mfa.verify).toHaveBeenCalledWith({
        factorId: "factor-1",
        challengeId: "challenge-1",
        code: "123456",
      })
    );
  });

  it("removes a verified factor only after confirmation", async () => {
    h.supabase.auth.mfa.listFactors.mockResolvedValue({
      data: { all: [VERIFIED_TOTP], totp: [VERIFIED_TOTP] },
      error: null,
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /^remove$/i }));
    expect(h.supabase.auth.mfa.unenroll).not.toHaveBeenCalled();

    // Confirm inside the dialog (its confirm button is also labeled Remove).
    const dialog = await screen.findByRole("dialog");
    const buttons = screen.getAllByRole("button", { name: /^remove$/i });
    fireEvent.click(buttons[buttons.length - 1]);

    await vi.waitFor(() =>
      expect(h.supabase.auth.mfa.unenroll).toHaveBeenCalledWith({
        factorId: "factor-1",
      })
    );
    expect(dialog).toBeDefined();
  });
});
