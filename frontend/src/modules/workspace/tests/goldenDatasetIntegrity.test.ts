/**
 * Golden Clinical Dataset integrity — architectural regression reference.
 * NOT a performance benchmark.
 */

import { describe, expect, it } from "vitest";
import {
  GOLDEN_CLINICAL_CONTENT,
  GOLDEN_NARRATIVE,
  GOLDEN_OBJECT_IDS,
  GOLDEN_WORKSPACE_PLAN,
} from "./goldenClinicalDataset";
import { CURRENTLY_SUPPORTED_OBJECT_IDS } from "../presentation/mappers/projectPlan";

const BODY_SLICES = [
  "patientHeader",
  "chiefComplaint",
  "redFlags",
  "snapshot",
  "timeline",
  "medications",
  "labs",
  "missingInfo",
  "soap",
  "documents",
] as const;

describe("Golden Clinical Dataset integrity", () => {
  it("documents itself as an architectural regression reference, not a benchmark", () => {
    // Structural presence of the golden pair is the regression anchor.
    expect(GOLDEN_WORKSPACE_PLAN.plan_etag).toBe("golden-etag-v1");
    expect(GOLDEN_CLINICAL_CONTENT.patientHeader?.name).toBe(GOLDEN_NARRATIVE.patientName);
  });

  it("includes all required clinical slices for a realistic patient", () => {
    expect(GOLDEN_CLINICAL_CONTENT.patientHeader).not.toBeNull();
    expect(GOLDEN_CLINICAL_CONTENT.chiefComplaint).not.toBeNull();
    expect(GOLDEN_CLINICAL_CONTENT.redFlags).not.toBeNull();
    expect(GOLDEN_CLINICAL_CONTENT.snapshot).not.toBeNull();
    expect(GOLDEN_CLINICAL_CONTENT.timeline).not.toBeNull();
    expect(GOLDEN_CLINICAL_CONTENT.medications).not.toBeNull();
    expect(GOLDEN_CLINICAL_CONTENT.labs).not.toBeNull();
    expect(GOLDEN_CLINICAL_CONTENT.documents).not.toBeNull();
    expect(GOLDEN_CLINICAL_CONTENT.soap).not.toBeNull();
    expect(GOLDEN_CLINICAL_CONTENT.missingInfo).not.toBeNull();

    expect(GOLDEN_CLINICAL_CONTENT.timeline!.groups.length).toBeGreaterThanOrEqual(16);
    expect(GOLDEN_CLINICAL_CONTENT.medications!.groups.length).toBeGreaterThanOrEqual(4);
    expect(GOLDEN_CLINICAL_CONTENT.labs!.rows.length).toBeGreaterThanOrEqual(10);
    expect(GOLDEN_CLINICAL_CONTENT.documents!.items.length).toBeGreaterThanOrEqual(5);
    expect(GOLDEN_CLINICAL_CONTENT.redFlags!.items.length).toBeGreaterThanOrEqual(2);
  });

  it("plan includes every catalog object_id exactly once", () => {
    const ids = GOLDEN_WORKSPACE_PLAN.layout_directives.map((d) => d.object_id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(new Set(ids)).toEqual(new Set(GOLDEN_OBJECT_IDS));
    expect(new Set(ids)).toEqual(CURRENTLY_SUPPORTED_OBJECT_IDS);
  });

  it("trust metadata never appears inside clinical body content", () => {
    for (const key of BODY_SLICES) {
      const slice = GOLDEN_CLINICAL_CONTENT[key];
      if (slice == null) continue;
      expect("trust" in (slice as object)).toBe(false);
    }
  });

  it("narrative anchors are stable and non-empty", () => {
    expect(GOLDEN_NARRATIVE.storyText.length).toBeGreaterThan(40);
    expect(GOLDEN_NARRATIVE.chiefComplaintTitle).toMatch(/chest/i);
    expect(GOLDEN_NARRATIVE.soapAssessment.length).toBeGreaterThan(80);
    expect(GOLDEN_NARRATIVE.soapPlan.length).toBeGreaterThan(80);
    expect(GOLDEN_WORKSPACE_PLAN.story?.text).toBe(GOLDEN_NARRATIVE.storyText);
  });

  it("pin_zone and hidden visibility remain consistent with directives", () => {
    const byId = new Map(
      GOLDEN_WORKSPACE_PLAN.layout_directives.map((d) => [d.object_id, d]),
    );
    for (const objectId of GOLDEN_WORKSPACE_PLAN.pin_zone) {
      const d = byId.get(objectId);
      expect(d).toBeDefined();
      expect(d!.slot).toBe("pin");
      expect(d!.pinned).toBe(true);
    }
    for (const d of GOLDEN_WORKSPACE_PLAN.layout_directives) {
      if (d.slot === "hidden") {
        expect(d.visibility_reason).not.toBeNull();
      } else {
        expect(d.visibility_reason).toBeNull();
      }
    }
  });
});
