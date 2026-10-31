import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// AuthGate's behavior hinges on VITE_SUPABASE_* env (read at module load in
// lib/supabase). We stub env, then dynamically import so the real supabase
// module re-evaluates against the stubbed values. Session-dependent flows
// (recovery, MFA) instead mock the supabase client via vi.doMock.
afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
  window.location.hash = "";
});

async function renderAuthGate() {
  const { AuthGate } = await import("./AuthGate");
  return render(
    <AuthGate>
      <div>PROTECTED CONTENT</div>
    </AuthGate>
  );
}

function fakeSupabase({
  session = null as unknown,
  aal = { currentLevel: "aal1", nextLevel: "aal1" },
  factors = [] as Array<Record<string, unknown>>,
} = {}) {
  return {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session } }),
      onAuthStateChange: vi
        .fn()
        .mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } }),
      signOut: vi.fn().mockResolvedValue({ error: null }),
      updateUser: vi.fn().mockResolvedValue({ error: null }),
      mfa: {
        getAuthenticatorAssuranceLevel: vi
          .fn()
          .mockResolvedValue({ data: aal, error: null }),
        listFactors: vi.fn().mockResolvedValue({
          data: { all: factors, totp: factors },
          error: null,
        }),
        challenge: vi
          .fn()
          .mockResolvedValue({ data: { id: "challenge-1" }, error: null }),
        verify: vi.fn().mockResolvedValue({ data: {}, error: null }),
      },
    },
  };
}

async function renderMockedAuthGate(client: ReturnType<typeof fakeSupabase>) {
  vi.doMock("../lib/supabase", () => ({ authEnabled: true, supabase: client }));
  const { AuthGate } = await import("./AuthGate");
  return render(
    <AuthGate>
      <div>PROTECTED CONTENT</div>
    </AuthGate>
  );
}

const SESSION = { user: { id: "user-1", email: "admin@example.com", app_metadata: {} } };
const VERIFIED_TOTP = { id: "factor-1", factor_type: "totp", status: "verified" };

describe("AuthGate", () => {
  it("fails closed when Supabase configuration is missing", async () => {
    vi.stubEnv("VITE_SUPABASE_URL", "");
    vi.stubEnv("VITE_SUPABASE_ANON_KEY", "");

    await renderAuthGate();
    expect(
      screen.getByRole("alert", { name: /authentication is not configured/i })
    ).toBeInTheDocument();
    expect(screen.queryByText("PROTECTED CONTENT")).not.toBeInTheDocument();
  });

  it("shows the login form (not the app) when auth is enabled and unauthenticated", async () => {
    vi.stubEnv("VITE_SUPABASE_URL", "https://demo.supabase.co");
    vi.stubEnv("VITE_SUPABASE_ANON_KEY", "test-anon-key");

    await renderAuthGate();

    expect(
      await screen.findByRole("button", { name: /sign in/i })
    ).toBeInTheDocument();
    expect(screen.queryByText("PROTECTED CONTENT")).not.toBeInTheDocument();
    // ToS acceptance belongs to account setup (the invite panel), not sign-in.
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });
});

describe("forgot password", () => {
  it("requests a reset link and always lands on the generic confirmation", async () => {
    vi.stubEnv("VITE_SUPABASE_URL", "https://demo.supabase.co");
    vi.stubEnv("VITE_SUPABASE_ANON_KEY", "test-anon-key");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "If an account exists..." }), {
        status: 200,
        headers: { "content-type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await renderAuthGate();
    fireEvent.click(
      await screen.findByRole("button", { name: /forgot password/i })
    );

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "admin@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send reset link/i }));

    expect(
      await screen.findByText(/if an account exists for that email/i)
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/auth/password-recovery");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      email: "admin@example.com",
    });
  });

  it("shows the same confirmation even when the request fails", async () => {
    vi.stubEnv("VITE_SUPABASE_URL", "https://demo.supabase.co");
    vi.stubEnv("VITE_SUPABASE_ANON_KEY", "test-anon-key");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    await renderAuthGate();
    fireEvent.click(
      await screen.findByRole("button", { name: /forgot password/i })
    );
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "admin@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send reset link/i }));

    expect(
      await screen.findByText(/if an account exists for that email/i)
    ).toBeInTheDocument();
  });

  it("explains an expired reset link on the login form", async () => {
    vi.stubEnv("VITE_SUPABASE_URL", "https://demo.supabase.co");
    vi.stubEnv("VITE_SUPABASE_ANON_KEY", "test-anon-key");
    window.location.hash =
      "#error=access_denied&error_code=otp_expired&error_description=x";

    await renderAuthGate();

    expect(
      await screen.findByText(/reset link has expired/i)
    ).toBeInTheDocument();
  });
});

describe("password recovery landing", () => {
  it("renders the new-password panel (no ToS gate) instead of the app", async () => {
    window.location.hash = "#access_token=x&type=recovery";
    const client = fakeSupabase({ session: SESSION });

    await renderMockedAuthGate(client);

    expect(
      await screen.findByRole("heading", { name: /choose a new password/i })
    ).toBeInTheDocument();
    expect(screen.queryByText("PROTECTED CONTENT")).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/new password/i), {
      target: { value: "s3cret-pass" },
    });
    fireEvent.change(screen.getByLabelText(/confirm password/i), {
      target: { value: "s3cret-pass" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save new password/i }));

    expect(await screen.findByText("PROTECTED CONTENT")).toBeInTheDocument();
    expect(client.auth.updateUser).toHaveBeenCalledWith({
      password: "s3cret-pass",
    });
  });
});

describe("MFA challenge gate", () => {
  it("blocks the app until the TOTP code verifies", async () => {
    const client = fakeSupabase({
      session: SESSION,
      aal: { currentLevel: "aal1", nextLevel: "aal2" },
      factors: [VERIFIED_TOTP],
    });

    await renderMockedAuthGate(client);

    expect(
      await screen.findByRole("heading", { name: /two-factor authentication/i })
    ).toBeInTheDocument();
    expect(screen.queryByText("PROTECTED CONTENT")).not.toBeInTheDocument();

    fireEvent.change(await screen.findByLabelText(/verification code/i), {
      target: { value: "123456" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^verify$/i }));

    expect(await screen.findByText("PROTECTED CONTENT")).toBeInTheDocument();
    expect(client.auth.mfa.challenge).toHaveBeenCalledWith({
      factorId: "factor-1",
    });
    expect(client.auth.mfa.verify).toHaveBeenCalledWith({
      factorId: "factor-1",
      challengeId: "challenge-1",
      code: "123456",
    });
  });

  it("lets an aal2 session straight through", async () => {
    const client = fakeSupabase({
      session: SESSION,
      aal: { currentLevel: "aal2", nextLevel: "aal2" },
    });

    await renderMockedAuthGate(client);

    expect(await screen.findByText("PROTECTED CONTENT")).toBeInTheDocument();
  });
});
