/**
 * Composition helper — maps plan object_id → feature content slice.
 * Owns the ClinicalContentViewModel ↔ card pairing so presenters never see the aggregate.
 */

import type { CardBodyContent, ClinicalContentViewModel } from "./types";
import type { HPIContent } from "./types/content";

export function selectClinicalSlice(
  objectId: string,
  clinicalContent: ClinicalContentViewModel | null | undefined,
): CardBodyContent | null {
  if (clinicalContent == null) return null;

  switch (objectId) {
    case "chief_complaint":
      return clinicalContent.chiefComplaint;
    case "hpi":
      return clinicalContent.hpi;
    case "red_flags":
      return clinicalContent.redFlags;
    case "snapshot":
      return clinicalContent.snapshot;
    case "pmh":
    case "allergies":
      return clinicalContent.snapshot;
    case "timeline":
      return clinicalContent.timeline;
    case "medications":
      return clinicalContent.medications;
    case "labs":
      return clinicalContent.labs;
    case "missing_data":
      return clinicalContent.missingInfo;
    case "soap":
      return clinicalContent.soap;
    case "documents":
      return clinicalContent.documents;
    default:
      return null;
  }
}
