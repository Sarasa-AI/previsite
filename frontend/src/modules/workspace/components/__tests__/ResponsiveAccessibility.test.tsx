import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CardChrome } from "../shared/CardChrome";
import { WorkspaceShell } from "../WorkspaceShell";
import { SourceDocumentsCard } from "../documents/SourceDocumentsCard";
import { LabsPanel } from "../labs/LabsPanel";
import { MedicationList } from "../medications/MedicationList";
import { makePlan } from "../../tests/fixtures";
import { projectPlan } from "../../presentation/mappers/projectPlan";
import { documentsFixture, labsFixture, medicationsFixture } from "./fixtures";

const noop = () => undefined;

function renderWorkspace() {
  return render(<WorkspaceShell uiState="Ready" viewModel={projectPlan(makePlan(), "responsive-etag")} error={null} onAcknowledge={noop} onRefreshStory={noop} onRetry={noop} onResolve={noop} onDismiss={noop} acknowledgePending={false} refreshStoryPending={false} resolvePending={false} dismissPending={false} clinicalContent={null} />);
}

describe("Doctor Workspace responsive and accessibility contracts", () => {
  it("contains horizontal overflow at the workspace and navigation boundaries", () => {
    const { container } = renderWorkspace();
    expect(container.querySelector("[data-workspace-shell]")).toHaveClass("overflow-x-clip");
    expect(screen.getByRole("navigation", { name: "Workspace navigation" })).toHaveClass("overflow-x-auto", "overscroll-x-contain");
    expect(screen.getByRole("main", { name: "Doctor workspace" })).toHaveClass("max-w-[1540px]");
  });

  it("keeps laptop workflow sticky but bounded to the viewport", () => {
    renderWorkspace();
    expect(screen.getByLabelText("Workspace workflow")).toHaveClass("xl:sticky", "xl:max-h-[calc(100dvh-1.5rem)]", "xl:overflow-y-auto", "xl:overscroll-contain");
  });

  it("preserves tablet, laptop and desktop grid breakpoints without changing hierarchy", () => {
    const { container } = renderWorkspace();
    expect(screen.getByLabelText("Workspace workflow").parentElement).toHaveClass("xl:grid-cols-[minmax(0,1fr)_15rem]", "2xl:grid-cols-[minmax(0,1fr)_17rem]");
    expect(container.querySelector('[data-workspace-band="secondary"]')).toHaveClass("md:grid-cols-2", "2xl:grid-cols-3");
    const pin = container.querySelector('[data-workspace-band="pin"]')!;
    const primary = container.querySelector('[data-workspace-band="primary"]')!;
    expect(pin.compareDocumentPosition(primary) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("provides semantic card headings and visible focus styles", () => {
    render(<CardChrome title="عنوان بالینی" aria-label="Clinical card">محتوا</CardChrome>);
    expect(screen.getByRole("heading", { level: 2, name: "عنوان بالینی" })).toBeInTheDocument();
    const { unmount } = renderWorkspace();
    expect(screen.getAllByRole("link")[0]).toHaveClass("focus-visible:ring-2", "focus-visible:ring-offset-1");
    unmount();
  });

  it("keeps mixed-direction values, doses, units and filenames bidi-safe", () => {
    const { rerender } = render(<MedicationList content={medicationsFixture} />);
    expect(screen.getByText("10 mg")).toHaveAttribute("dir", "ltr");
    expect(screen.getByText("Lisinopril")).toHaveAttribute("dir", "auto");
    rerender(<LabsPanel content={labsFixture} />);
    expect(screen.getByText("0.08")).toHaveAttribute("dir", "ltr");
    expect(screen.getByText("ng/mL")).toHaveAttribute("dir", "ltr");
    rerender(<SourceDocumentsCard content={documentsFixture} />);
    expect(screen.getByText("ED triage note.pdf")).toHaveAttribute("dir", "auto");
  });

  it("does not communicate lab severity by color alone", () => {
    render(<LabsPanel content={labsFixture} />);
    expect(screen.getByText("غیرطبیعی")).toHaveAttribute("data-clinical-value-state", "abnormal");
    expect(screen.getByText("غیرطبیعی").querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByText("طبیعی")).toHaveAttribute("data-clinical-value-state", "normal");
  });
});
