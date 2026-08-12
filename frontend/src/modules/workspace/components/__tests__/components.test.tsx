import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CardChrome } from "../shared/CardChrome";
import { TrustBadge } from "../shared/TrustBadge";
import { EmptyState } from "../shared/EmptyState";
import { ErrorState } from "../shared/ErrorState";
import { PatientHeader } from "../layout/PatientHeader";
import { ClinicalSnapshotStrip } from "../layout/ClinicalSnapshotStrip";
import { ChiefComplaintCard } from "../cards/ChiefComplaintCard";
import { RedFlagsCard } from "../cards/RedFlagsCard";
import { MissingInformationCard } from "../cards/MissingInformationCard";
import { SoapPreviewCard } from "../cards/SoapPreviewCard";
import { Timeline } from "../timeline/Timeline";
import { MedicationList } from "../medications/MedicationList";
import { LabsPanel } from "../labs/LabsPanel";
import { SourceDocumentsCard } from "../documents/SourceDocumentsCard";
import {
  ChiefComplaintSkeleton,
  DocumentsSkeleton,
  LabsPanelSkeleton,
  MedicationListSkeleton,
  MissingInfoSkeleton,
  PatientHeaderSkeleton,
  RedFlagsSkeleton,
  SnapshotStripSkeleton,
  SoapSkeleton,
  TimelineSkeleton,
} from "../skeletons";
import {
  chiefComplaintFixture,
  documentsFixture,
  labsFixture,
  medicationsFixture,
  missingInfoFixture,
  patientHeaderFixture,
  redFlagsFixture,
  snapshotStripFixture,
  soapFixture,
  timelineFixture,
  trustFixture,
} from "./fixtures";

describe("CardChrome", () => {
  it("renders all slots", () => {
    render(
      <CardChrome
        title="Title"
        subtitle="Subtitle"
        badges={<span>Badge</span>}
        trust={<span>Trust</span>}
        actions={<button type="button">Act</button>}
        footer="Footer"
      >
        Body
      </CardChrome>,
    );

    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getByText("Subtitle")).toBeInTheDocument();
    expect(screen.getByText("Badge")).toBeInTheDocument();
    expect(screen.getByText("Trust")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Act" })).toBeInTheDocument();
    expect(screen.getByText("Body")).toBeInTheDocument();
    expect(screen.getByText("Footer")).toBeInTheDocument();
  });

  it("matches snapshot", () => {
    const { container } = render(
      <CardChrome title="Snapshot" trust={<span>T</span>}>
        Content
      </CardChrome>,
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});

describe("TrustBadge", () => {
  it("renders verification and confidence as chrome", () => {
    render(<TrustBadge trust={trustFixture} />);
    expect(screen.getByLabelText(/Trust: verified/i)).toBeInTheDocument();
    expect(screen.getByText("verified")).toBeInTheDocument();
    expect(screen.getByText("92%")).toBeInTheDocument();
  });
});

describe("PatientHeader", () => {
  it("renders demographics and separate trust chrome", () => {
    render(
      <PatientHeader content={patientHeaderFixture} trust={<TrustBadge trust={trustFixture} />} />,
    );
    expect(screen.getByText("Jane Doe")).toBeInTheDocument();
    expect(screen.getByText(/MRN MRN-10042/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Status Arrived/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Trust: verified/i)).toBeInTheDocument();
  });

  it("renders empty demographics state", () => {
    render(<PatientHeader content={null} />);
    expect(screen.getByText(/demographics are not available/i)).toBeInTheDocument();
  });

  it("supports RTL container", () => {
    const { container } = render(
      <div dir="rtl">
        <PatientHeader content={patientHeaderFixture} />
      </div>,
    );
    expect(container.querySelector("[dir='rtl']")).toBeTruthy();
    expect(screen.getByLabelText("Patient header")).toBeInTheDocument();
  });

  it("matches snapshot", () => {
    const { container } = render(<PatientHeader content={patientHeaderFixture} />);
    expect(container.firstChild).toMatchSnapshot();
  });
});

describe("ClinicalSnapshotStrip", () => {
  it("renders metrics", () => {
    render(<ClinicalSnapshotStrip content={snapshotStripFixture} />);
    expect(screen.getByText("Vitals")).toBeInTheDocument();
    expect(screen.getByText("BP 138/86 · HR 88")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("renders empty state", () => {
    render(<ClinicalSnapshotStrip content={null} />);
    expect(screen.getByText("No snapshot")).toBeInTheDocument();
  });
});

describe("ChiefComplaintCard", () => {
  it("renders title, duration, priority", () => {
    render(<ChiefComplaintCard content={chiefComplaintFixture} />);
    expect(screen.getByText("Chest tightness")).toBeInTheDocument();
    expect(screen.getByText("3 days")).toBeInTheDocument();
    expect(screen.getByLabelText("Priority p1")).toBeInTheDocument();
  });

  it("renders empty state", () => {
    render(<ChiefComplaintCard content={null} />);
    expect(screen.getByText("No chief complaint")).toBeInTheDocument();
  });
});

describe("RedFlagsCard", () => {
  it("renders severity items and expands explanation", async () => {
    const user = userEvent.setup();
    render(<RedFlagsCard content={redFlagsFixture} />);
    expect(screen.getByText("Exertional dyspnea")).toBeInTheDocument();
    expect(screen.getByText("critical")).toBeInTheDocument();

    await user.click(screen.getByText("Exertional dyspnea"));
    expect(screen.getByText(/rule out ACS/i)).toBeInTheDocument();
  });

  it("renders empty state", () => {
    render(<RedFlagsCard content={{ items: [] }} />);
    expect(screen.getByText("No red flags")).toBeInTheDocument();
  });
});

describe("MissingInformationCard", () => {
  it("renders checklist and action placeholder", () => {
    render(<MissingInformationCard content={missingInfoFixture} />);
    expect(screen.getByLabelText("Last ECG date")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request update" })).toBeInTheDocument();
  });
});

describe("SoapPreviewCard", () => {
  it("renders assessment and plan sections", async () => {
    const user = userEvent.setup();
    render(<SoapPreviewCard content={soapFixture} />);
    await user.click(screen.getByText("Assessment"));
    expect(screen.getByText(/unstable angina/i)).toBeInTheDocument();
    await user.click(screen.getByText("Plan"));
    expect(screen.getByText(/Serial troponins/i)).toBeInTheDocument();
  });

  it("can start expanded", () => {
    render(<SoapPreviewCard content={soapFixture} defaultExpanded />);
    expect(screen.getByText(/unstable angina/i)).toBeVisible();
    expect(screen.getByText(/Serial troponins/i)).toBeVisible();
  });
});

describe("Timeline", () => {
  it("groups events by date with source", async () => {
    const user = userEvent.setup();
    render(<Timeline content={timelineFixture} />);
    expect(screen.getByText("2026-08-01")).toBeInTheDocument();
    expect(screen.getByText("ED visit")).toBeInTheDocument();
    expect(screen.getByLabelText("Source ehr")).toBeInTheDocument();
    await user.click(screen.getByText("ED visit"));
    expect(screen.getByText(/troponin pending/i)).toBeInTheDocument();
  });
});

describe("MedicationList", () => {
  it("renders grouped medications", () => {
    render(<MedicationList content={medicationsFixture} />);
    expect(screen.getByText("Cardiovascular")).toBeInTheDocument();
    expect(screen.getByText("Lisinopril")).toBeInTheDocument();
    expect(screen.getByText(/10 mg · daily/)).toBeInTheDocument();
  });
});

describe("LabsPanel", () => {
  it("highlights abnormal rows and expands detail", async () => {
    const user = userEvent.setup();
    render(<LabsPanel content={labsFixture} />);
    expect(screen.getByText("Troponin I")).toHaveClass("text-danger");
    await user.click(screen.getByText("Troponin I"));
    expect(screen.getByText(/Rising vs prior/i)).toBeInTheDocument();
  });
});

describe("SourceDocumentsCard", () => {
  it("renders file metadata", async () => {
    const user = userEvent.setup();
    render(<SourceDocumentsCard content={documentsFixture} />);
    expect(screen.getByText("ED triage note.pdf")).toBeInTheDocument();
    expect(screen.getByLabelText("Confidence 88%")).toBeInTheDocument();
    await user.click(screen.getByText("ED triage note.pdf"));
    expect(screen.getByText(/Extracted vitals/i)).toBeInTheDocument();
  });
});

describe("Empty and Error states", () => {
  it("renders empty state", () => {
    render(<EmptyState title="Empty" message="Nothing here" />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-label", "Empty");
  });

  it("renders error state without retry", () => {
    render(<ErrorState title="Failed" message="Could not load" />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("Skeletons", () => {
  const cases = [
    ["PatientHeaderSkeleton", PatientHeaderSkeleton, "Loading patient header"],
    ["SnapshotStripSkeleton", SnapshotStripSkeleton, "Loading clinical snapshot"],
    ["ChiefComplaintSkeleton", ChiefComplaintSkeleton, "Loading chief complaint"],
    ["RedFlagsSkeleton", RedFlagsSkeleton, "Loading red flags"],
    ["TimelineSkeleton", TimelineSkeleton, "Loading timeline"],
    ["MedicationListSkeleton", MedicationListSkeleton, "Loading medications"],
    ["LabsPanelSkeleton", LabsPanelSkeleton, "Loading labs"],
    ["MissingInfoSkeleton", MissingInfoSkeleton, "Loading missing information"],
    ["SoapSkeleton", SoapSkeleton, "Loading SOAP preview"],
    ["DocumentsSkeleton", DocumentsSkeleton, "Loading source documents"],
  ] as const;

  it.each(cases)("%s renders busy status with reduced-motion safe pulse", (_name, Comp, label) => {
    const { container } = render(<Comp />);
    expect(screen.getByRole("status", { name: label })).toHaveAttribute("aria-busy", "true");
    const bone = container.querySelector(".animate-pulse");
    expect(bone).toBeTruthy();
    expect(bone?.className).toContain("motion-reduce:animate-none");
  });
});

describe("Contrast / token classes (WCAG AA pairings)", () => {
  it("uses high-contrast token classes for critical and body text", () => {
    const { container } = render(<RedFlagsCard content={redFlagsFixture} />);
    expect(container.querySelector(".text-danger")).toBeTruthy();
    expect(container.querySelector(".text-trust")).toBeTruthy();
  });

  it("error title uses danger on white", () => {
    const { container } = render(<ErrorState title="Err" message="msg" />);
    const title = within(container).getByText("Err");
    expect(title.className).toContain("text-danger");
  });
});

describe("Architecture: trust not in content fixtures", () => {
  it("patient header content has no trust field", () => {
    expect(patientHeaderFixture).not.toHaveProperty("trust");
    expect(chiefComplaintFixture).not.toHaveProperty("trust");
    expect(labsFixture).not.toHaveProperty("trust");
  });
});
