import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WidgetPreview } from "./WidgetPreview";
import type { AppearanceState } from "./WidgetAppearance";

const appearance: AppearanceState = {
  accentColor: "#0284c7",
  launcherIcon: "chat",
  launcherPosition: "bottom-right",
  greeting: "Welcome! Ask me anything.",
  launcherLabel: "",
};

describe("WidgetPreview", () => {
  it("renders the assistant name and greeting", () => {
    render(
      <WidgetPreview
        appearance={appearance}
        assistantName="Aria"
        businessName="Acme"
        showBranding
      />
    );
    expect(screen.getByText("Aria")).toBeInTheDocument();
    expect(screen.getByText("Welcome! Ask me anything.")).toBeInTheDocument();
    expect(screen.getByText("Plug & Play")).toBeInTheDocument();
  });

  it("hides branding when disabled", () => {
    render(
      <WidgetPreview
        appearance={appearance}
        assistantName="Aria"
        businessName="Acme"
        showBranding={false}
      />
    );
    expect(screen.queryByText("Plug & Play")).toBeNull();
  });
});
