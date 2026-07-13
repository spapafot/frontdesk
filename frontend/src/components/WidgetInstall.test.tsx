import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { WidgetInstall } from "./WidgetInstall";

function snippetText(props: Partial<Parameters<typeof WidgetInstall>[0]> = {}) {
  const { container } = render(
    <MemoryRouter>
      <WidgetInstall
        siteKey="pk_test123"
        accentColor="#ff8800"
        launcherIcon="sparkles"
        launcherPosition="bottom-left"
        greeting='Hello "there"'
        launcherLabel="Chat now"
        showBranding
        onRotate={async () => {}}
        {...props}
      />
    </MemoryRouter>
  );
  return container.querySelector("pre")?.textContent ?? "";
}

describe("WidgetInstall snippet", () => {
  it("embeds the chosen appearance as data-* attributes", () => {
    const snippet = snippetText();
    expect(snippet).toContain('data-site-key="pk_test123"');
    expect(snippet).toContain('data-accent="#ff8800"');
    expect(snippet).toContain('data-position="bottom-left"');
    expect(snippet).toContain('data-icon="sparkles"');
    expect(snippet).toContain('data-launcher-label="Chat now"');
  });

  it("escapes quotes in the greeting attribute", () => {
    expect(snippetText()).toContain('data-greeting="Hello &quot;there&quot;"');
  });

  it("omits the launcher label when empty", () => {
    expect(snippetText({ launcherLabel: "" })).not.toContain("data-launcher-label");
  });

  it("adds data-branding only when branding is disabled", () => {
    expect(snippetText({ showBranding: true })).not.toContain("data-branding");
    expect(snippetText({ showBranding: false })).toContain('data-branding="false"');
  });

  it("renders nothing without a site key", () => {
    const { container } = render(
      <MemoryRouter>
        <WidgetInstall
          siteKey={null}
          accentColor="#0284c7"
          launcherIcon="chat"
          launcherPosition="bottom-right"
          greeting="Hi"
          launcherLabel=""
          showBranding
          onRotate={async () => {}}
        />
      </MemoryRouter>
    );
    expect(container.querySelector("pre")).toBeNull();
  });
});
