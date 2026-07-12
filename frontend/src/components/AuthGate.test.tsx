import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// AuthGate's behavior hinges on VITE_SUPABASE_* env (read at module load in
// lib/supabase). We stub env, then dynamically import so the real supabase
// module re-evaluates against the stubbed values.
afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.resetModules();
});

async function renderAuthGate() {
  const { AuthGate } = await import("./AuthGate");
  return render(
    <AuthGate>
      <div>PROTECTED CONTENT</div>
    </AuthGate>
  );
}

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
  });
});
