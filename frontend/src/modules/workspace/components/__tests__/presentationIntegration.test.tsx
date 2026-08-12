import { describe, expect, it, vi } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { render, screen, within } from "@testing-library/react";
import { WorkspaceShell } from "../WorkspaceShell";
import { projectPlan } from "../../presentation/mappers/projectPlan";
import { makeDirective, makePlan } from "../../tests/fixtures";
import { selectClinicalSlice } from "../selectClinicalSlice";
import {
  ChiefComplaintPresenter,
  DocumentsPresenter,
  LabsPresenter,
  MedicationsPresenter,
  MissingDataPresenter,
  RedFlagsPresenter,
  SnapshotPresenter,
  SoapPresenter,
  TimelinePresenter,
} from "../presenters";
import type { CardViewModel } from "../../presentation/viewmodels/types";
import {
  emptyClinicalContent,
  largeClinicalContent,
  partialClinicalContent,
} from "./clinicalDatasets";
import {
  GOLDEN_CLINICAL_CONTENT,
  GOLDEN_NARRATIVE,
  GOLDEN_WORKSPACE_PLAN,
} from "../../tests/goldenClinicalDataset";

const noop = vi.fn();

const baseTrust = {
  primaryProvenance: "ehr",
  allProvenance: ["ehr", "patient_report"] as const,
  confidence: 0.91 as const,
  verification: "verified",
  evidenceRefs: ["ev-int-1"] as const,
};

function makeCard(objectId: string, overrides: Partial<CardViewModel> = {}): CardViewModel {
  return {
    objectId,
    priority: "p1",
    slot: "primary",
    size: "standard",
    pinned: false,
    trust: { ...baseTrust, allProvenance: [...baseTrust.allProvenance], evidenceRefs: [...baseTrust.evidenceRefs] },
    flags: [],
    ...overrides,
  };
}

function integrationPlan() {
  return makePlan({
    layout_directives: [
      makeDirective({ object_id: "critical_alerts", slot: "pin", priority: "p0", size: "expanded", pinned: true }),
      makeDirective({ object_id: "chief_complaint", slot: "primary", priority: "p0" }),
      makeDirective({ object_id: "red_flags", slot: "primary", priority: "p0" }),
      makeDirective({ object_id: "timeline", slot: "primary", priority: "p1" }),
      makeDirective({ object_id: "labs", slot: "primary", priority: "p1" }),
      makeDirective({ object_id: "medications", slot: "primary", priority: "p2" }),
      makeDirective({ object_id: "missing_data", slot: "secondary", priority: "p2" }),
      makeDirective({ object_id: "soap", slot: "secondary", priority: "p2", size: "expanded" }),
      makeDirective({ object_id: "documents", slot: "deferred", priority: "p3", size: "compressed" }),
      makeDirective({ object_id: "snapshot", slot: "secondary", priority: "p2" }),
    ],
    pin_zone: ["critical_alerts"],
  });
}

describe("selectClinicalSlice", () => {
  it("returns feature slices only (never the aggregate)", () => {
    expect(selectClinicalSlice("timeline", largeClinicalContent)).toBe(largeClinicalContent.timeline);
    expect(selectClinicalSlice("labs", largeClinicalContent)).toBe(largeClinicalContent.labs);
    expect(selectClinicalSlice("medications", largeClinicalContent)).toBe(largeClinicalContent.medications);
    expect(selectClinicalSlice("critical_alerts", largeClinicalContent)).toBeNull();
    expect(selectClinicalSlice("timeline", null)).toBeNull();
  });
});

describe("Presenter feature-slice rendering", () => {
  it("renders chief complaint body and trust chrome from slice", () => {
    render(
      <ChiefComplaintPresenter
        card={makeCard("chief_complaint")}
        content={largeClinicalContent.chiefComplaint}
      />,
    );
    expect(screen.getByText(/Exertional chest tightness/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Trust: verified/i)).toBeInTheDocument();
  });

  it("renders red flags from slice", () => {
    render(
      <RedFlagsPresenter card={makeCard("red_flags")} content={largeClinicalContent.redFlags} />,
    );
    expect(screen.getByText("Exertional dyspnea")).toBeInTheDocument();
    expect(screen.getByText("Recent syncope")).toBeInTheDocument();
  });

  it("renders long timeline from slice", () => {
    render(
      <TimelinePresenter card={makeCard("timeline")} content={largeClinicalContent.timeline} />,
    );
    expect(largeClinicalContent.timeline!.groups.length).toBeGreaterThanOrEqual(16);
    expect(screen.getByLabelText("Timeline")).toBeInTheDocument();
    expect(screen.getAllByText("ED triage").length).toBeGreaterThan(1);
    expect(screen.getAllByLabelText(/Events on /i).length).toBeGreaterThan(5);
  });

  it("renders large medication lists from slice", () => {
    render(
      <MedicationsPresenter
        card={makeCard("medications")}
        content={largeClinicalContent.medications}
      />,
    );
    expect(screen.getByText("Cardiovascular")).toBeInTheDocument();
    expect(screen.getByText("Endocrine")).toBeInTheDocument();
    expect(screen.getByText("Lisinopril")).toBeInTheDocument();
    expect(screen.getByText("Metformin")).toBeInTheDocument();
  });

  it("renders large lab panels from slice", () => {
    render(<LabsPresenter card={makeCard("labs")} content={largeClinicalContent.labs} />);
    expect(screen.getByText("Troponin I")).toBeInTheDocument();
    expect(screen.getByText("Creatinine")).toBeInTheDocument();
    expect(screen.getByText("Hemoglobin")).toBeInTheDocument();
    expect(screen.getByText("LDL")).toBeInTheDocument();
    expect(largeClinicalContent.labs!.rows.length).toBeGreaterThan(10);
  });

  it("renders document lists from slice", () => {
    render(
      <DocumentsPresenter card={makeCard("documents")} content={largeClinicalContent.documents} />,
    );
    expect(screen.getByText("ED triage note.pdf")).toBeInTheDocument();
    expect(screen.getByText("Echo report.pdf")).toBeInTheDocument();
  });

  it("renders missing information from slice", () => {
    render(
      <MissingDataPresenter
        card={makeCard("missing_data")}
        content={largeClinicalContent.missingInfo}
      />,
    );
    expect(screen.getByText("Last ECG date")).toBeInTheDocument();
    expect(screen.getByText("Smoking status")).toBeInTheDocument();
  });

  it("renders large SOAP from slice", () => {
    render(
      <SoapPresenter
        card={makeCard("soap", { size: "expanded" })}
        content={largeClinicalContent.soap}
      />,
    );
    expect(screen.getByText(/Likely unstable angina/i)).toBeInTheDocument();
    expect(screen.getByText(/Serial troponins/i)).toBeInTheDocument();
  });

  it("renders snapshot strip from slice", () => {
    render(
      <SnapshotPresenter card={makeCard("snapshot")} content={largeClinicalContent.snapshot} />,
    );
    expect(screen.getByText(/BP 148\/92/i)).toBeInTheDocument();
    expect(screen.getByText(/High CV/i)).toBeInTheDocument();
  });

  it("handles null content with empty states", () => {
    render(<TimelinePresenter card={makeCard("timeline")} content={null} />);
    expect(screen.getByText("No timeline events")).toBeInTheDocument();

    render(<LabsPresenter card={makeCard("labs")} content={null} />);
    expect(screen.getByText("No labs")).toBeInTheDocument();

    render(<MedicationsPresenter card={makeCard("medications")} content={null} />);
    expect(screen.getByText("No medications")).toBeInTheDocument();
  });
});

describe("WorkspaceShell clinical content integration", () => {
  it("renders patient header and clinical bodies from large dataset", () => {
    const viewModel = projectPlan(integrationPlan(), "etag-large");
    render(
      <WorkspaceShell
        uiState="Ready"
        viewModel={viewModel}
        error={null}
        clinicalContent={largeClinicalContent}
        onAcknowledge={noop}
        onRefreshStory={noop}
        onRetry={noop}
      />,
    );

    expect(screen.getByText("Margaret Chen")).toBeInTheDocument();
    expect(screen.getByText(/MRN-884201/)).toBeInTheDocument();
    expect(screen.getByText(/Exertional chest tightness/i)).toBeInTheDocument();
    expect(screen.getByText("Exertional dyspnea")).toBeInTheDocument();
    expect(screen.getByText("Lisinopril")).toBeInTheDocument();
    expect(screen.getByText("Troponin I")).toBeInTheDocument();
    expect(screen.getByText(/BP 148\/92/i)).toBeInTheDocument();
    expect(screen.getByText("Last ECG date")).toBeInTheDocument();
    expect(screen.getByText(/Likely unstable angina/i)).toBeInTheDocument();

    const deferred = document.querySelector('[data-workspace-band="deferred"]') as HTMLDetailsElement;
    expect(deferred).toBeTruthy();
    expect(within(deferred).getByText("ED triage note.pdf")).toBeInTheDocument();

    expect(screen.getAllByLabelText(/Trust: verified/i).length).toBeGreaterThan(0);
  });

  it("handles partial / null clinical slices without throwing", () => {
    const viewModel = projectPlan(integrationPlan(), "etag-partial");
    render(
      <WorkspaceShell
        uiState="Ready"
        viewModel={viewModel}
        error={null}
        clinicalContent={partialClinicalContent}
        onAcknowledge={noop}
        onRefreshStory={noop}
        onRetry={noop}
      />,
    );

    expect(screen.getByText("Alex Rivera")).toBeInTheDocument();
    expect(screen.getByText("Palpitations")).toBeInTheDocument();
    expect(screen.getByText("No timeline events")).toBeInTheDocument();
    expect(screen.getByText("No medications")).toBeInTheDocument();
    expect(screen.getByText("No labs")).toBeInTheDocument();
    expect(screen.getByText("No SOAP preview")).toBeInTheDocument();
    expect(screen.getByText("No documents")).toBeInTheDocument();
    expect(screen.getByText("Baseline ECG")).toBeInTheDocument();
  });

  it("renders empty clinical aggregate as empty states", () => {
    const viewModel = projectPlan(integrationPlan(), "etag-empty");
    render(
      <WorkspaceShell
        uiState="Ready"
        viewModel={viewModel}
        error={null}
        clinicalContent={emptyClinicalContent}
        onAcknowledge={noop}
        onRefreshStory={noop}
        onRetry={noop}
      />,
    );

    expect(screen.getByText(/Patient demographics are not available/i)).toBeInTheDocument();
    expect(screen.getByText("No chief complaint")).toBeInTheDocument();
  });
});

describe("Golden dataset: Shell semantic rendering", () => {
  it("region order and card identity match ViewModel bands", () => {
    const viewModel = projectPlan(GOLDEN_WORKSPACE_PLAN, GOLDEN_WORKSPACE_PLAN.plan_etag);
    const { container } = render(
      <WorkspaceShell
        uiState="Ready"
        viewModel={viewModel}
        error={null}
        clinicalContent={GOLDEN_CLINICAL_CONTENT}
        onAcknowledge={noop}
        onRefreshStory={noop}
        onRetry={noop}
      />,
    );

    const pin = container.querySelector('[data-workspace-band="pin"]');
    const primary = container.querySelector('[data-workspace-band="primary"]');
    const secondary = container.querySelector('[data-workspace-band="secondary"]');
    const deferred = container.querySelector('[data-workspace-band="deferred"]');

    expect(
      [...(pin?.querySelectorAll("[data-workspace-card]") ?? [])].map((el) =>
        el.getAttribute("data-workspace-card"),
      ),
    ).toEqual(viewModel.pinCards.map((c) => c.objectId));

    expect(
      [...(primary?.querySelectorAll("[data-workspace-card]") ?? [])].map((el) =>
        el.getAttribute("data-workspace-card"),
      ),
    ).toEqual(viewModel.primaryCards.map((c) => c.objectId));

    expect(
      [...(secondary?.querySelectorAll("[data-workspace-card]") ?? [])].map((el) =>
        el.getAttribute("data-workspace-card"),
      ),
    ).toEqual(viewModel.secondaryCards.map((c) => c.objectId));

    expect(
      [...(deferred?.querySelectorAll("[data-workspace-card]") ?? [])].map((el) =>
        el.getAttribute("data-workspace-card"),
      ),
    ).toEqual(viewModel.deferredCards.map((c) => c.objectId));

    // Hidden cards never render
    expect(container.querySelector('[data-workspace-card="conflicts"]')).toBeNull();
    expect(container.querySelector('[data-workspace-card="critical_labs"]')).toBeNull();
  });

  it("preserves priority and trust chrome; narrative text is verbatim", () => {
    const viewModel = projectPlan(GOLDEN_WORKSPACE_PLAN, GOLDEN_WORKSPACE_PLAN.plan_etag);
    const { container } = render(
      <WorkspaceShell
        uiState="Ready"
        viewModel={viewModel}
        error={null}
        clinicalContent={GOLDEN_CLINICAL_CONTENT}
        onAcknowledge={noop}
        onRefreshStory={noop}
        onRetry={noop}
      />,
    );

    for (const card of viewModel.pinCards) {
      const el = container.querySelector(`[data-workspace-card="${card.objectId}"]`);
      expect(el?.getAttribute("data-priority")).toBe(card.priority);
      expect(el?.getAttribute("data-slot")).toBe("pin");
    }

    expect(screen.getByText(GOLDEN_NARRATIVE.patientName)).toBeInTheDocument();
    expect(screen.getByText(GOLDEN_NARRATIVE.chiefComplaintTitle)).toBeInTheDocument();

    const story = container.querySelector("[data-story]");
    expect(story?.textContent).toContain(GOLDEN_NARRATIVE.storyText);

    expect(screen.getByText(/Likely unstable angina vs NSTEMI/i)).toBeInTheDocument();
    expect(screen.getByText(/Serial troponins q3h/i)).toBeInTheDocument();

    // Trust chrome from plan — not fabricated into body
    expect(screen.getAllByLabelText(/Trust:/i).length).toBeGreaterThan(0);
    expect("trust" in (GOLDEN_CLINICAL_CONTENT.chiefComplaint as object)).toBe(false);
  });

  it("each card renders only its assigned clinical slice (card semantics)", () => {
    const viewModel = projectPlan(GOLDEN_WORKSPACE_PLAN, GOLDEN_WORKSPACE_PLAN.plan_etag);
    const { container } = render(
      <WorkspaceShell
        uiState="Ready"
        viewModel={viewModel}
        error={null}
        clinicalContent={GOLDEN_CLINICAL_CONTENT}
        onAcknowledge={noop}
        onRefreshStory={noop}
        onRetry={noop}
      />,
    );

    const cc = container.querySelector('[data-workspace-card="chief_complaint"]');
    expect(cc?.textContent).toContain(GOLDEN_NARRATIVE.chiefComplaintTitle);
    expect(cc?.textContent).not.toContain("Lisinopril");
    expect(cc?.textContent).not.toContain("Troponin I");

    const meds = container.querySelector('[data-workspace-card="medications"]');
    expect(meds?.textContent).toContain("Lisinopril");
    expect(meds?.textContent).not.toContain(GOLDEN_NARRATIVE.chiefComplaintTitle);

    const labs = container.querySelector('[data-workspace-card="labs"]');
    expect(labs?.textContent).toContain("Troponin I");
    expect(labs?.textContent).not.toContain("Lisinopril");
  });
});

describe("Architecture: presentation integration", () => {
  it("content ViewModels do not embed trust", () => {
    expect("trust" in (largeClinicalContent.patientHeader as object)).toBe(false);
    expect("trust" in (largeClinicalContent.chiefComplaint as object)).toBe(false);
    expect("trust" in (largeClinicalContent.timeline as object)).toBe(false);
    expect("trust" in (largeClinicalContent.labs as object)).toBe(false);
  });

  it("presenters do not import ClinicalContentViewModel", () => {
    const presentersPath = path.join(__dirname, "../presenters/index.tsx");
    const source = readFileSync(presentersPath, "utf8");
    expect(source).not.toMatch(/ClinicalContentViewModel/);
    expect(source).not.toMatch(/content=\{null\}/);
    expect(source).not.toMatch(/from ["'].*api/);
    expect(source).not.toMatch(/\bfetch\b/);
    expect(source).not.toMatch(/useQuery|react-query|@tanstack\/react-query/);
    expect(source).not.toMatch(/\buse[A-Z]\w*\(/);
  });

  it("composition selector owns the aggregate pairing", () => {
    const selectorPath = path.join(__dirname, "../selectClinicalSlice.ts");
    const source = readFileSync(selectorPath, "utf8");
    expect(source).toMatch(/ClinicalContentViewModel/);
    expect(source).toMatch(/objectId/);
  });

  it("stubs directory remains absent", () => {
    const stubsPath = path.join(__dirname, "../stubs");
    expect(existsSync(stubsPath)).toBe(false);
  });
});
