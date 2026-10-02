export type ChronicCondition = {
  id: string;
  name: string;
  duration: string;
};

export type ConditionFile = {
  id: number;
  filename: string;
  size: number;
  mime_type: string;
  condition_id: string | null;
  url?: string;
};

export type LabResult = {
  id: string;
  name: string;
  /** Intake write/autofill only — clinician UI must not consume; use GET /documents/:id/ocr */
  extracted_data?: string;
};

/** Immutable snapshot of DrugYab catalog facts captured at selection time. */
export type MedicationCatalogSnapshot = {
  catalog_id?: number | null;
  brand_name?: string | null;
  brand_name_fa?: string | null;
  brand_name_en?: string | null;
  generic_name?: string | null;
  generic_name_en?: string | null;
  generic_slug?: string | null;
  brand_slug?: string | null;
  strength_raw?: string | null;
  dosage_form?: string | null;
  manufacturer?: string | null;
  company_name?: string | null;
  company_slug?: string | null;
};

/** Prescription-level instructions. Never sourced from the DrugYab catalog. */
export type MedicationPrescription = {
  dose?: string | null;
  dose_unit?: string | null;
  quantity?: string | null;
  frequency?: string | null;
  duration?: string | null;
  route?: string | null;
  instructions?: string | null;
};

export type MedicationProvenance = {
  source?: string;
  confidence?: number | null;
  verification_status?: string;
};

export type CurrentMedication = {
  id: string;
  catalog_id?: number | null;
  name: string;
  amount: string;
  frequency: string;
  dose_unit?: string | null;
  catalog?: MedicationCatalogSnapshot | null;
  prescription?: MedicationPrescription | null;
  provenance?: MedicationProvenance | null;
};

export type MedicalOverview = {
  allergies: string;
  surgical_history: string;
  family_history: string;
  chronic_conditions: ChronicCondition[];
  current_medications: CurrentMedication[];
  lab_results: LabResult[];
  file_condition_map?: Record<number, string>;
  patient_questions?: string | null;
};

export const emptyMedicalOverview: MedicalOverview = {
  allergies: "",
  surgical_history: "",
  family_history: "",
  chronic_conditions: [],
  current_medications: [],
  lab_results: [],
  patient_questions: null,
};
