/**
 * Near-identity ClinicalContentResponse → ClinicalContentViewModel mapping tests.
 */

import { describe, expect, it } from "vitest";
import type { ClinicalContentResponse } from "../api/types";
import { projectClinicalContent } from "../presentation/mappers/projectClinicalContent";

const FULL_RESPONSE: ClinicalContentResponse = {
  session_id: 42,
  context_hash: "abc123",
  content_version: "1.0.0",
  generated_at: "2026-07-28T15:00:00+00:00",
  content: {
    patient_header: {
      name: "Jane Doe",
      age: 54,
      sex: "female",
      mrn: "MRN-10042",
      visit_type: "Follow-up",
      status: "active",
    },
    chief_complaint: {
      title: "Chest tightness",
      duration: "3 days",
      priority: "",
    },
    red_flags: {
      items: [
        {
          id: "rf-1",
          title: "Syncope",
          severity: "critical",
          explanation: "Syncope",
        },
      ],
    },
    snapshot: {
      vitals: "",
      problems: "HTN, T2DM",
      risk: "",
      allergies: "Penicillin",
      medication_count: 2,
      timeline_count: 4,
    },
    timeline: {
      groups: [
        {
          date: "2026-07-20",
          events: [
            {
              id: "e0",
              title: "Onset",
              detail: "Started suddenly",
              source: "hpi",
            },
          ],
        },
      ],
    },
    medications: {
      groups: [
        {
          label: "Current",
          items: [
            {
              id: "m1",
              name: "Metformin",
              dose: "500mg",
              frequency: "BID",
              status: "active",
              source: "clinical_context",
            },
          ],
        },
      ],
    },
    labs: {
      rows: [
        {
          id: "l1",
          name: "BMP",
          value: "Potassium 6.5 critical",
          unit: "",
          reference_range: "",
          abnormal: true,
          trend: "unknown",
          detail: "Potassium 6.5 critical",
        },
      ],
    },
    missing_info: null,
    soap: {
      assessment: "Possible ACS",
      plan: "Troponin serials",
    },
    documents: {
      items: [
        {
          id: "10",
          name: "labs.pdf",
          confidence: "unknown",
          uploaded_at: "2026-07-27T10:00:00+00:00",
          detail: "",
        },
      ],
    },
  },
};

describe("projectClinicalContent", () => {
  it("maps full envelope content to ClinicalContentViewModel", () => {
    const vm = projectClinicalContent(FULL_RESPONSE);
    expect(vm.patientHeader?.name).toBe("Jane Doe");
    expect(vm.patientHeader?.visitType).toBe("Follow-up");
    expect(vm.chiefComplaint?.title).toBe("Chest tightness");
    expect(vm.redFlags?.items[0]?.severity).toBe("critical");
    expect(vm.snapshot?.medicationCount).toBe(2);
    expect(vm.snapshot?.timelineCount).toBe(4);
    expect(vm.timeline?.groups[0]?.events[0]?.title).toBe("Onset");
    expect(vm.medications?.groups[0]?.items[0]?.name).toBe("Metformin");
    expect(vm.labs?.rows[0]?.referenceRange).toBe("");
    expect(vm.labs?.rows[0]?.abnormal).toBe(true);
    expect(vm.soap?.assessment).toBe("Possible ACS");
    expect(vm.documents?.items[0]?.uploadedAt).toBe("2026-07-27T10:00:00+00:00");
    expect(vm.missingInfo).toBeNull();
  });

  it("preserves null slices", () => {
    const vm = projectClinicalContent({
      session_id: 1,
      context_hash: "h",
      content_version: "1.0.0",
      generated_at: "2026-07-28T15:00:00+00:00",
      content: {
        patient_header: null,
        chief_complaint: null,
        red_flags: null,
        snapshot: null,
        timeline: null,
        medications: null,
        labs: null,
        missing_info: null,
        soap: null,
        documents: null,
      },
    });
    expect(vm.patientHeader).toBeNull();
    expect(vm.chiefComplaint).toBeNull();
    expect(vm.redFlags).toBeNull();
    expect(vm.timeline).toBeNull();
    expect(vm.medications).toBeNull();
    expect(vm.labs).toBeNull();
    expect(vm.documents).toBeNull();
    expect(vm.soap).toBeNull();
  });

  it("does not invent clinical fields", () => {
    const vm = projectClinicalContent(FULL_RESPONSE);
    expect(vm.snapshot?.vitals).toBe("");
    expect(vm.snapshot?.risk).toBe("");
    expect(vm.chiefComplaint?.priority).toBe("");
  });
});
