import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import ProgressIndicator from "./ProgressIndicator";

const LABELS = ["اطلاعات اولیه", "شرح حال", "خلاصه بالینی", "سوابق پزشکی", "ارسال"];

describe("ProgressIndicator", () => {
  it("renders five layer chips", () => {
    render(<ProgressIndicator currentLayer={1} labels={LABELS} />);
    expect(screen.getByTestId("progress-indicator").children).toHaveLength(5);
  });

  it("marks layer 1 as active when currentLayer is 1", () => {
    render(<ProgressIndicator currentLayer={1} labels={LABELS} />);
    expect(screen.getByTestId("progress-chip-1")).toHaveAttribute("data-active", "true");
    expect(screen.getByTestId("progress-chip-2")).toHaveAttribute("data-active", "false");
    expect(screen.getByTestId("progress-chip-1")).toHaveAttribute("data-done", "false");
  });

  it("marks prior layers as done when on layer 3", () => {
    render(<ProgressIndicator currentLayer={3} labels={LABELS} />);
    expect(screen.getByTestId("progress-chip-1")).toHaveAttribute("data-done", "true");
    expect(screen.getByTestId("progress-chip-2")).toHaveAttribute("data-done", "true");
    expect(screen.getByTestId("progress-chip-3")).toHaveAttribute("data-active", "true");
    expect(screen.getByTestId("progress-chip-1").textContent).toContain("✓");
  });

  it("shows numeric prefix for incomplete layers", () => {
    render(<ProgressIndicator currentLayer={2} labels={LABELS} />);
    expect(screen.getByTestId("progress-chip-2").textContent).toMatch(/^2\./);
    expect(screen.getByTestId("progress-chip-5").textContent).toMatch(/^5\./);
  });

  it("marks all prior chips done on final layer", () => {
    render(<ProgressIndicator currentLayer={5} labels={LABELS} />);
    for (let i = 1; i <= 4; i += 1) {
      expect(screen.getByTestId(`progress-chip-${i}`)).toHaveAttribute("data-done", "true");
    }
    expect(screen.getByTestId("progress-chip-5")).toHaveAttribute("data-active", "true");
  });
});
