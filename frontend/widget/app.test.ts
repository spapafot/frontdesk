import { beforeEach, describe, expect, it, vi } from "vitest";

describe("embedded widget verification flow", () => {
  beforeEach(() => {
    vi.resetModules();
    document.body.innerHTML = '<div id="app"></div>';
    history.replaceState(
      null,
      "",
      `/#${new URLSearchParams({
        origin: location.origin,
        api: "https://api.example",
        turnstileSiteKey: "site-key",
      })}`
    );
  });

  it("renders Turnstile on first open and sends its token only to the parent origin", async () => {
    let success: ((token: string) => void) | undefined;
    const render = vi.fn((_container, options) => {
      success = options.callback;
      return "widget-id";
    });
    window.turnstile = { render, reset: vi.fn() };
    const postMessage = vi.spyOn(window, "postMessage");

    await import("./app");
    window.dispatchEvent(new Event("load"));
    success?.("challenge-token");

    expect(render).toHaveBeenCalledWith(
      "#wx-turnstile",
      expect.objectContaining({
        sitekey: "site-key",
        action: "widget-session",
        size: "flexible",
      })
    );
    expect(postMessage).toHaveBeenCalledWith(
      { type: "wx-turnstile", token: "challenge-token" },
      location.origin
    );
  });

  it("keeps chat hidden until an origin-checked signed session arrives", async () => {
    window.turnstile = {
      render: vi.fn(() => "widget-id"),
      reset: vi.fn(),
    };
    await import("./app");

    const form = document.getElementById("wx-form") as HTMLFormElement;
    expect(form.hidden).toBe(true);

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "https://attacker.example",
        source: window,
        data: { type: "wx-session", session: { token: "attacker" } },
      })
    );
    expect(form.hidden).toBe(true);

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: location.origin,
        source: window,
        data: {
          type: "wx-session",
          session: {
            token: "signed-session",
            installation_id: 17,
            origin: "https://customer.example",
            assistant_name: "Helper",
            business_name: "Acme",
          },
        },
      })
    );

    expect(form.hidden).toBe(false);
    expect(document.getElementById("wx-title")).toHaveTextContent("Helper");
  });
});

describe("widget appearance", () => {
  beforeEach(() => {
    vi.resetModules();
    document.body.innerHTML = '<div id="app"></div>';
    document.documentElement.removeAttribute("style");
  });

  function setHash(extra: Record<string, string>) {
    history.replaceState(
      null,
      "",
      `/#${new URLSearchParams({ origin: location.origin, api: "https://api.example", ...extra })}`
    );
  }

  it("shows the Powered by Plug & Play footer by default", async () => {
    setHash({});
    await import("./app");
    const footer = document.getElementById("wx-branding") as HTMLElement;
    expect(footer.hidden).toBe(false);
    expect(footer).toHaveTextContent("Powered by Plug & Play");
  });

  it("hides branding when branding=false", async () => {
    setHash({ branding: "false" });
    await import("./app");
    expect((document.getElementById("wx-branding") as HTMLElement).hidden).toBe(true);
  });

  it("derives readable text color from the accent", async () => {
    setHash({ accent: "#0284c7" }); // dark accent -> white text
    await import("./app");
    expect(document.documentElement.style.getPropertyValue("--accent-contrast")).toBe("#ffffff");
  });

  it("uses dark text on a light accent", async () => {
    setHash({ accent: "#fde047" }); // light yellow -> dark text
    await import("./app");
    expect(document.documentElement.style.getPropertyValue("--accent-contrast")).toBe("#0f172a");
  });
});
