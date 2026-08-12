/**
 * Representative clinical content datasets for presentation integration tests.
 * Avoid toy sizes — long timeline, multi-group meds, multi-panel labs, documents, large SOAP.
 */

import type { ClinicalContentViewModel } from "../types";

function freezeDeep<T>(value: T): T {
  return Object.freeze(value) as T;
}

const TIMELINE_TITLES = [
  "ED triage",
  "Troponin draw",
  "ECG completed",
  "Cardiology consult",
  "Primary care visit",
  "Medication adjustment",
  "Outpatient labs",
  "Imaging review",
  "Pharmacy refill",
  "Nurse call follow-up",
] as const;

function buildTimelineGroups(count: number) {
  const groups = [];
  for (let g = 0; g < count; g += 1) {
    const day = String(30 - (g % 28)).padStart(2, "0");
    const month = String(8 - Math.floor(g / 28)).padStart(2, "0");
    const date = `2026-${month}-${day}`;
    const events = [];
    for (let e = 0; e < 3; e += 1) {
      const idx = (g * 3 + e) % TIMELINE_TITLES.length;
      events.push(
        freezeDeep({
          id: `te-${g}-${e}`,
          title: TIMELINE_TITLES[idx],
          detail: `${TIMELINE_TITLES[idx]} documented for visit day ${g + 1}; source note excerpt ${g}-${e}.`,
          source: e % 2 === 0 ? "ehr" : "clinic_note",
        }),
      );
    }
    groups.push(freezeDeep({ date, events: freezeDeep(events) }));
  }
  return freezeDeep(groups);
}

const MED_GROUPS: { label: string; names: readonly string[] }[] = [
  {
    label: "Cardiovascular",
    names: ["Lisinopril", "Metoprolol", "Atorvastatin", "Aspirin", "Clopidogrel", "Amlodipine"],
  },
  {
    label: "Endocrine",
    names: ["Metformin", "Empagliflozin", "Glipizide", "Levothyroxine", "Semaglutide"],
  },
  {
    label: "Respiratory",
    names: ["Albuterol", "Fluticasone", "Montelukast", "Tiotropium"],
  },
  {
    label: "Gastrointestinal",
    names: ["Omeprazole", "Ondansetron", "Docusate"],
  },
];

function buildMedications() {
  const groups = MED_GROUPS.map((group, gi) =>
    freezeDeep({
      label: group.label,
      items: freezeDeep(
        group.names.map((name, ni) =>
          freezeDeep({
            id: `med-${gi}-${ni}`,
            name,
            dose: ni % 2 === 0 ? "10 mg" : "500 mg",
            frequency: ni % 3 === 0 ? "daily" : "BID",
            status: ni === 0 ? "active" : "active",
            source: ni % 2 === 0 ? "ehr" : "patient_report",
          }),
        ),
      ),
    }),
  );
  return freezeDeep({ groups: freezeDeep(groups) });
}

const LAB_PANELS = [
  {
    panel: "Cardiac",
    rows: [
      ["Troponin I", "0.08", "ng/mL", "<0.04", true, "up"],
      ["BNP", "210", "pg/mL", "<100", true, "up"],
      ["CK-MB", "4.2", "ng/mL", "0–5", false, "stable"],
    ],
  },
  {
    panel: "Metabolic",
    rows: [
      ["Creatinine", "0.9", "mg/dL", "0.6–1.2", false, "stable"],
      ["eGFR", "78", "mL/min", ">60", false, "down"],
      ["Glucose", "142", "mg/dL", "70–99", true, "up"],
      ["Potassium", "4.1", "mmol/L", "3.5–5.1", false, "stable"],
      ["Sodium", "138", "mmol/L", "136–145", false, "stable"],
    ],
  },
  {
    panel: "Hematology",
    rows: [
      ["Hemoglobin", "13.2", "g/dL", "12–16", false, "stable"],
      ["WBC", "9.4", "10^3/uL", "4–11", false, "stable"],
      ["Platelets", "238", "10^3/uL", "150–400", false, "stable"],
    ],
  },
  {
    panel: "Lipid",
    rows: [
      ["LDL", "118", "mg/dL", "<100", true, "up"],
      ["HDL", "42", "mg/dL", ">40", false, "stable"],
      ["Triglycerides", "165", "mg/dL", "<150", true, "up"],
    ],
  },
] as const;

function buildLabs() {
  const rows = [];
  let id = 0;
  for (const panel of LAB_PANELS) {
    for (const [name, value, unit, referenceRange, abnormal, trend] of panel.rows) {
      id += 1;
      rows.push(
        freezeDeep({
          id: `lab-${id}`,
          name,
          value,
          unit,
          referenceRange,
          abnormal,
          trend: trend as "up" | "down" | "stable" | "unknown",
          detail: `${panel.panel} panel · prior comparison available.`,
        }),
      );
    }
  }
  return freezeDeep({ rows: freezeDeep(rows) });
}

function buildDocuments() {
  const names = [
    "ED triage note.pdf",
    "Prior ECG.png",
    "Cardiology consult.pdf",
    "Discharge summary.pdf",
    "Medication reconciliation.pdf",
    "Chest X-ray report.pdf",
    "Echo report.pdf",
    "Insurance referral.pdf",
  ];
  return freezeDeep({
    items: freezeDeep(
      names.map((name, i) =>
        freezeDeep({
          id: `doc-${i + 1}`,
          name,
          confidence: i % 3 === 0 ? ("unknown" as const) : 0.7 + i * 0.03,
          uploadedAt: `2026-07-${String(10 + i).padStart(2, "0")}T09:00:00Z`,
          detail: `Extracted clinical fields from ${name}; OCR quality ${i % 2 === 0 ? "high" : "moderate"}.`,
        }),
      ),
    ),
  });
}

const LARGE_SOAP_ASSESSMENT = [
  "Likely unstable angina vs NSTEMI in the setting of known CAD and diabetes.",
  "Differential includes demand ischemia from anemia, PE (lower likelihood given no hypoxia), and GERD.",
  "Risk stratification: TIMI intermediate; HEART score elevated on history and ECG changes.",
  "Comorbidities: HTN, T2DM, hyperlipidemia, prior NSTEMI (2023), CKD stage 2.",
  "Social: lives alone; limited transportation; medication adherence historically uneven.",
].join("\n\n");

const LARGE_SOAP_PLAN = [
  "Serial troponins q3h × 3; continuous telemetry; repeat ECG with chest pain.",
  "ASA 325 mg load then 81 mg daily; heparin per ACS protocol unless bleeding risk rises.",
  "Cardiology consult for early invasive strategy; hold NSAIDs; continue beta-blocker.",
  "Optimize diabetes: hold metformin if contrast anticipated; check A1c if not recent.",
  "Patient education on red-flag symptoms; arrange PCP follow-up within 7 days if discharged.",
  "Address missing data: last ECG date, smoking status, statin intolerance history.",
].join("\n\n");

/** Full realistic clinical content aggregate for integration tests. */
export const largeClinicalContent: ClinicalContentViewModel = freezeDeep({
  patientHeader: freezeDeep({
    name: "Margaret Chen",
    age: 67,
    sex: "F",
    mrn: "MRN-884201",
    visitType: "Urgent follow-up",
    status: "Arrived",
  }),
  chiefComplaint: freezeDeep({
    title: "Exertional chest tightness with dyspnea for 3 days",
    duration: "3 days",
    priority: "p0",
  }),
  redFlags: freezeDeep({
    items: freezeDeep([
      freezeDeep({
        id: "rf-1",
        title: "Exertional dyspnea",
        severity: "critical" as const,
        explanation: "Worsening with mild activity; concerning for ACS.",
      }),
      freezeDeep({
        id: "rf-2",
        title: "Recent syncope",
        severity: "warning" as const,
        explanation: "Single episode yesterday; no head trauma reported.",
      }),
      freezeDeep({
        id: "rf-3",
        title: "Diaphoresis with pain",
        severity: "warning" as const,
        explanation: "Associated sweating during last episode of tightness.",
      }),
    ]),
  }),
  snapshot: freezeDeep({
    vitals: "BP 148/92 · HR 94 · SpO2 96% RA · Temp 36.8",
    problems: "CAD, HTN, T2DM, HLD, CKD2",
    risk: "High CV — prior NSTEMI",
    allergies: "Penicillin (rash), Sulfa (hives)",
    medicationCount: 18,
    timelineCount: 48,
  }),
  timeline: freezeDeep({ groups: buildTimelineGroups(16) }),
  medications: buildMedications(),
  labs: buildLabs(),
  missingInfo: freezeDeep({
    items: freezeDeep([
      freezeDeep({ id: "mi-1", label: "Last ECG date", priority: "p1" }),
      freezeDeep({ id: "mi-2", label: "Smoking status", priority: "p1" }),
      freezeDeep({ id: "mi-3", label: "Statin intolerance history", priority: "p2" }),
      freezeDeep({ id: "mi-4", label: "Most recent A1c", priority: "p2" }),
      freezeDeep({ id: "mi-5", label: "Contrast allergy confirmation", priority: "p1" }),
      freezeDeep({ id: "mi-6", label: "Advance directive on file", priority: "p3" }),
    ]),
    actionLabel: "Request update",
  }),
  soap: freezeDeep({
    assessment: LARGE_SOAP_ASSESSMENT,
    plan: LARGE_SOAP_PLAN,
  }),
  documents: buildDocuments(),
});

/** Partial aggregate — null / missing optional clinical slices. */
export const partialClinicalContent: ClinicalContentViewModel = freezeDeep({
  patientHeader: freezeDeep({
    name: "Alex Rivera",
    age: 41,
    sex: "M",
    mrn: "MRN-11002",
    visitType: "New consult",
    status: "Checked in",
  }),
  chiefComplaint: freezeDeep({
    title: "Palpitations",
    duration: "2 weeks",
    priority: "p2",
  }),
  redFlags: null,
  snapshot: null,
  timeline: freezeDeep({ groups: freezeDeep([]) }),
  medications: null,
  labs: freezeDeep({ rows: freezeDeep([]) }),
  missingInfo: freezeDeep({
    items: freezeDeep([
      freezeDeep({ id: "mi-a", label: "Baseline ECG", priority: "p1" }),
    ]),
    actionLabel: "Request update",
  }),
  soap: null,
  documents: null,
});

/** All clinical body slices null. */
export const emptyClinicalContent: ClinicalContentViewModel = freezeDeep({
  patientHeader: null,
  chiefComplaint: null,
  redFlags: null,
  snapshot: null,
  timeline: null,
  medications: null,
  labs: null,
  missingInfo: null,
  soap: null,
  documents: null,
});
