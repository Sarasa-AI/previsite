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
import { AllergiesCard, ProblemsCard } from "../clinical/ClinicalDataCards";
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
    expect(screen.getAllByText("نامشخص")).toHaveLength(2);
    expect(screen.getByLabelText(/Status Arrived/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Trust: verified/i)).toBeInTheDocument();
  });

  it("renders empty demographics state", () => {
    render(<PatientHeader content={null} />);
    expect(screen.getByText(/مشخصات جمعیت‌شناختی بیمار در دسترس نیست/)).toBeInTheDocument();
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
    expect(screen.getAllByText("BP 138/86 · HR 88").length).toBeGreaterThan(0);
    expect(screen.getAllByText("در دسترس نیست")).toHaveLength(6);
    expect(screen.queryByText("Normal")).not.toBeInTheDocument();
  });

  it("renders empty state", () => {
    render(<ClinicalSnapshotStrip content={null} />);
    expect(screen.getByText("No snapshot")).toBeInTheDocument();
    expect(screen.queryByText(/No .*negative/i)).not.toBeInTheDocument();
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
    expect(screen.getByText(/شکایت اصلی ثبت نشده/)).toBeInTheDocument();
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
    expect(screen.getByText(/به معنی طبیعی بودن یا رد خطر نیست/)).toBeInTheDocument();
  });
});

describe("MissingInformationCard", () => {
  it("renders checklist and action placeholder", () => {
    render(<MissingInformationCard content={missingInfoFixture} />);
    expect(screen.getByText("Last ECG date")).toBeInTheDocument();
    expect(screen.getAllByText("مفقود")).toHaveLength(2);
    expect(screen.getAllByText("در قرارداد فعلی موجود نیست")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Request update" })).toBeInTheDocument();
  });
});

describe("SoapPreviewCard", () => {
  it("renders all four sections without inventing unavailable content", () => {
    render(<SoapPreviewCard content={soapFixture} />);
    expect(screen.getByLabelText("Subjective / ذهنی")).toHaveTextContent("در قرارداد فعلی موجود نیست");
    expect(screen.getByLabelText("Objective / عینی")).toHaveTextContent("در قرارداد فعلی موجود نیست");
    expect(screen.getByLabelText("Assessment / ارزیابی")).toBeInTheDocument();
    expect(screen.getByText(/unstable angina/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Plan / برنامه")).toBeInTheDocument();
    expect(screen.getByText(/Serial troponins/i)).toBeInTheDocument();
  });

  it("can start expanded", () => {
    render(<SoapPreviewCard content={soapFixture} defaultExpanded />);
    expect(screen.getByText(/unstable angina/i)).toBeVisible();
    expect(screen.getByText(/Serial troponins/i)).toBeVisible();
  });
});

describe("Timeline", () => {
  it("groups events by date with source and provenance", async () => {
    const user = userEvent.setup();
    render(<Timeline content={timelineFixture} provenance={trustFixture} />);
    expect(screen.getAllByText("2026-08-01").length).toBeGreaterThan(0);
    expect(screen.getByText("ED visit")).toBeInTheDocument();
    expect(screen.getByLabelText("Source ehr")).toBeInTheDocument();
    expect(screen.getByText(/troponin pending/i)).toBeInTheDocument();
    expect(screen.getAllByText("در قرارداد موجود نیست")).toHaveLength(2);
    await user.click(screen.getAllByText("منشأ و شواهد")[0]!);
    expect(screen.getByLabelText("Provenance for ED visit")).toBeInTheDocument();
    expect(screen.getAllByText("ev-1").length).toBeGreaterThan(0);
  });

  it("renders explicit loading, error, unavailable and empty states", () => {
    const { rerender } = render(<Timeline content={null} state="loading" />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
    rerender(<Timeline content={null} state="error" />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    rerender(<Timeline content={null} state="unavailable" />);
    expect(screen.getByText("خط زمانی در دسترس نیست")).toBeInTheDocument();
    rerender(<Timeline content={null} />);
    expect(screen.getByText("رویدادی ثبت نشده است")).toBeInTheDocument();
  });
});

describe("MedicationList", () => {
  it("renders grouped medications", () => {
    render(<MedicationList content={medicationsFixture} />);
    expect(screen.getByText("Cardiovascular")).toBeInTheDocument();
    expect(screen.getByText("Lisinopril")).toBeInTheDocument();
    expect(screen.getByText("10 mg")).toBeInTheDocument();
    expect(screen.getByText("daily")).toBeInTheDocument();
    expect(screen.getAllByText("نامشخص").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Source ehr")).toBeInTheDocument();
  });
});

describe("LabsPanel", () => {
  it("shows contract-backed status and explicit unavailable timestamp", () => {
    render(<LabsPanel content={labsFixture} />);
    expect(screen.getByText("Troponin I")).toHaveClass("text-danger");
    expect(screen.getByText(/Rising vs prior/i)).toBeInTheDocument();
    expect(screen.getAllByText("در دسترس نیست")).toHaveLength(4);
    expect(screen.getByText("غیرطبیعی")).toBeInTheDocument();
    expect(screen.getByText("طبیعی")).toBeInTheDocument();
  });
});

describe("Clinical data summary cards", () => {
  it("shows problems without fabricating status or supporting evidence", () => {
    render(<ProblemsCard content={snapshotStripFixture} />);
    expect(screen.getByText("HTN, T2DM")).toBeInTheDocument();
    expect(screen.getByText("نامشخص")).toBeInTheDocument();
    expect(screen.getByText("در قرارداد فعلی موجود نیست")).toBeInTheDocument();
  });

  it("keeps allergy missing, unknown, NKDA and conflict distinct", () => {
    const { rerender } = render(<AllergiesCard content={null} />);
    expect(screen.getByText("مستندسازی موجود نیست")).toHaveAttribute("data-semantic-state", "missing");
    rerender(<AllergiesCard content={snapshotStripFixture} />);
    expect(screen.getByText("معنا/وضعیت نامشخص")).toHaveAttribute("data-semantic-state", "unknown");
    rerender(<AllergiesCard content={snapshotStripFixture} state="nkda" />);
    expect(screen.getByText("NKDA ثبت‌شده")).toHaveAttribute("data-semantic-state", "verified");
    rerender(<AllergiesCard content={snapshotStripFixture} state="conflict" />);
    expect(screen.getByText("تعارض حل‌نشده")).toHaveAttribute("data-semantic-state", "conflict");
  });
});

describe("SourceDocumentsCard", () => {
  it("renders contract metadata, provenance and in-workspace detail", async () => {
    const user = userEvent.setup();
    render(<SourceDocumentsCard content={documentsFixture} provenance={trustFixture} />);
    expect(screen.getByText("ED triage note.pdf")).toBeInTheDocument();
    expect(screen.getByText(/نوع: PDF/)).toBeInTheDocument();
    expect(screen.getByText("تایید نشده")).toHaveAttribute("data-semantic-state", "unverified");
    await user.click(screen.getByRole("button", { name: "View details ED triage note.pdf" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText("Confidence 88%")).toBeInTheDocument();
    expect(screen.getByText(/Extracted vitals/i)).toBeInTheDocument();
    expect(screen.getByText("پیش‌نمایش اصل سند در دسترس نیست")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("renders explicit loading, error, unavailable and empty states", () => {
    const { rerender } = render(<SourceDocumentsCard content={null} state="loading" />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
    rerender(<SourceDocumentsCard content={null} state="error" />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    rerender(<SourceDocumentsCard content={null} state="unavailable" />);
    expect(screen.getByText("اسناد در دسترس نیست")).toBeInTheDocument();
    rerender(<SourceDocumentsCard content={null} />);
    expect(screen.getByText("سندی ثبت نشده است")).toBeInTheDocument();
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
