import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ClinicalValueState, StatePanel, type ClinicalUiState, type ClinicalValueStateKind } from "@/components/ui";
import { AllergiesCard } from "../clinical/ClinicalDataCards";
import { LabsPanel } from "../labs/LabsPanel";
import { MedicationList } from "../medications/MedicationList";
import { EmptyState } from "../shared/EmptyState";
import { labsFixture, medicationsFixture, snapshotStripFixture } from "./fixtures";

const matrix: readonly ClinicalValueStateKind[] = [
  "confirmed", "normal", "abnormal", "unknown", "missing", "unavailable",
  "not-verified", "conflict", "resolved", "stale", "ai-generated", "draft",
  "confirmed-by-physician",
];
const uiMatrix: readonly ClinicalUiState[] = ["loading", "empty", "partial", "error", "unknown", "missing", "unavailable", "conflict", "not-verified", "stale"];

describe("clinical state semantic matrix", () => {
  it.each(matrix)("renders %s with text, icon-independent semantics and an accessible label", (state) => {
    const { container } = render(<ClinicalValueState state={state} />);
    const value = container.querySelector(`[data-clinical-value-state="${state}"]`);
    expect(value).toBeInTheDocument();
    expect(value).toHaveAttribute("aria-label");
    expect(value).not.toBeEmptyDOMElement();
    expect(value?.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("keeps safety-critical pairs semantically distinct", () => {
    const { container } = render(<>{matrix.map((state) => <ClinicalValueState key={state} state={state} />)}</>);
    expect(container.querySelector('[data-clinical-value-state="unknown"]')).not.toHaveAttribute("data-semantic-state", "normal");
    expect(container.querySelector('[data-clinical-value-state="missing"]')).not.toHaveAttribute("data-semantic-state", "normal");
    expect(container.querySelector('[data-clinical-value-state="conflict"]')).not.toHaveAttribute("data-semantic-state", "resolved");
    expect(container.querySelector('[data-clinical-value-state="not-verified"]')).not.toHaveAttribute("data-semantic-state", "verified");
    expect(container.querySelector('[data-clinical-value-state="draft"]')).not.toHaveAttribute("data-semantic-state", "physician-confirmed");
    expect(container.querySelector('[data-clinical-value-state="ai-generated"]')).not.toHaveAttribute("data-semantic-state", "verified");
  });

  it.each(uiMatrix)("standardizes the %s presentation state", (kind) => {
    render(<StatePanel kind={kind} title={`state-${kind}`} />);
    const panel = screen.getByText(`state-${kind}`).closest("div[data-clinical-ui-state]");
    expect(panel).toHaveAttribute("data-clinical-ui-state", kind);
    expect(panel).toHaveAttribute("aria-live", kind === "error" || kind === "conflict" ? "assertive" : "polite");
    if (kind === "loading") expect(panel).toHaveAttribute("aria-busy", "true");
  });

  it("distinguishes empty, missing and unavailable UI states", () => {
    const { rerender } = render(<EmptyState title="خالی" message="موردی ثبت نشده است" />);
    expect(screen.getByRole("status")).toHaveAttribute("data-clinical-ui-state", "empty");
    rerender(<EmptyState state="missing" title="ثبت نشده" message="مستندی وجود ندارد" />);
    expect(screen.getByRole("status")).toHaveAttribute("data-clinical-ui-state", "missing");
    rerender(<EmptyState state="unavailable" title="در دسترس نیست" message="داده قابل دریافت نیست" />);
    expect(screen.getByRole("status")).toHaveAttribute("data-clinical-ui-state", "unavailable");
  });

  it("keeps allergy states explicit without resolving contract ambiguity", () => {
    const { rerender } = render(<AllergiesCard content={snapshotStripFixture} />);
    expect(screen.getByText("معنا/وضعیت نامشخص")).toHaveAttribute("data-clinical-value-state", "unknown");
    rerender(<AllergiesCard content={snapshotStripFixture} state="nkda" />);
    expect(screen.getByText("NKDA ثبت‌شده")).toHaveAttribute("data-clinical-value-state", "confirmed");
    rerender(<AllergiesCard content={snapshotStripFixture} state="confirmed" />);
    expect(screen.getByText("حساسیت تاییدشده")).toHaveAttribute("data-clinical-value-state", "confirmed");
    rerender(<AllergiesCard content={snapshotStripFixture} state="conflict" />);
    expect(screen.getByText("تعارض حل‌نشده")).toHaveAttribute("data-clinical-value-state", "conflict");
    expect(screen.queryByText("حل‌شده")).not.toBeInTheDocument();
  });

  it("uses only the lab contract abnormal flag for normality", () => {
    render(<LabsPanel content={labsFixture} />);
    expect(screen.getByText("غیرطبیعی")).toHaveAttribute("data-clinical-value-state", "abnormal");
    expect(screen.getByText("طبیعی")).toHaveAttribute("data-clinical-value-state", "normal");
    expect(screen.getAllByText("در دسترس نیست")[0]).toHaveAttribute("data-clinical-value-state", "unavailable");
  });

  it("does not render medication contract status as verified or normal", () => {
    render(<MedicationList content={medicationsFixture} />);
    for (const status of screen.getAllByText("active")) {
      expect(status).toHaveAttribute("data-clinical-value-state", "not-verified");
      expect(status).not.toHaveAttribute("data-semantic-state", "verified");
    }
  });
});
