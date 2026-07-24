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

export type CurrentMedication = {
  id: string;
  name: string;
  amount: string;
  frequency: string;
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
