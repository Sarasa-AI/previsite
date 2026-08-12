/**
 * Card Registry — lookup only.
 * Resolves presentation components. Never determines visibility, ordering,
 * priority, layout, attention, or workflow behavior (those come from WorkspacePlan).
 */

import { emitWorkspaceTelemetry } from "@/src/shared/utils/telemetry";
import { CURRENTLY_SUPPORTED_OBJECT_IDS } from "../mappers/projectPlan";
import type { CardPresenter } from "./types";

import {
  AllergiesPresenter,
  ChiefComplaintPresenter,
  ConflictsPresenter,
  CriticalAlertsPresenter,
  CriticalLabsPresenter,
  DocumentsPresenter,
  LabsPresenter,
  MedicationsPresenter,
  MissingDataPresenter,
  PatientQuestionsPresenter,
  PmhPresenter,
  RedFlagsPresenter,
  SnapshotPresenter,
  SoapPresenter,
  StoryPresenter,
  TimelinePresenter,
} from "../../components/presenters";

export type { CardPresenter, CardPresenterProps } from "./types";

const REGISTRY: Record<string, CardPresenter> = {
  chief_complaint: ChiefComplaintPresenter,
  red_flags: RedFlagsPresenter,
  critical_alerts: CriticalAlertsPresenter,
  conflicts: ConflictsPresenter,
  allergies: AllergiesPresenter,
  timeline: TimelinePresenter,
  story: StoryPresenter,
  labs: LabsPresenter,
  critical_labs: CriticalLabsPresenter,
  medications: MedicationsPresenter,
  pmh: PmhPresenter,
  documents: DocumentsPresenter,
  patient_questions: PatientQuestionsPresenter,
  missing_data: MissingDataPresenter,
  soap: SoapPresenter,
  snapshot: SnapshotPresenter,
};

export function resolveCardPresenter(
  objectId: string,
  context?: {
    sessionId?: number;
    planEtag?: string;
    contractVersion?: string;
  },
): CardPresenter | null {
  const presenter = REGISTRY[objectId];
  if (presenter) return presenter;

  emitWorkspaceTelemetry("workspace.unknown_object_id", {
    object_id: objectId,
    session_id: context?.sessionId,
    plan_etag: context?.planEtag,
    contract_version: context?.contractVersion,
  });
  return null;
}

export function listRegisteredObjectIds(): readonly string[] {
  return Object.freeze(Object.keys(REGISTRY));
}

export function isRegisteredObjectId(objectId: string): boolean {
  return objectId in REGISTRY;
}

export { CURRENTLY_SUPPORTED_OBJECT_IDS, REGISTRY as cardRegistryMap };
