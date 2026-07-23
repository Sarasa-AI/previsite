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

// @deprecated — retained for unused PMH components
export type PMHSchema = PMHCategory[];

export type PMHCategory = {
  category_id: string;
  farsi_title: string;
  master_patient_text: string;
  questions: PMHQuestion[];
};

export type PMHQuestion = {
  id: string;
  category: string;
  subcategory: string;
  priority: number;
  ui_type: "checkbox" | "text_input" | string;
  patient_text: string;
  physician_metadata: {
    concept: string;
    icd10_hint?: string | null;
    snomed_ct?: string | null;
  };
  conditional_followups?: PMHFollowup[];
};

export type PMHFollowup = {
  id: string;
  ui_type: "text_input" | "date" | "select" | string;
  patient_text: string;
  physician_metadata?: string;
};

export type PMHAnswer = {
  category_id: string;
  is_selected: boolean;
  question_responses: Record<string, boolean | string>;
};

export type PMHSubmission = {
  patient_id: number;
  answers: PMHAnswer[];
};

export type PMHAnswersState = {
  selectedPrimary: Record<string, boolean>;
  followupValues: Record<string, string>;
};

export const emptyPMHAnswersState: PMHAnswersState = {
  selectedPrimary: {},
  followupValues: {},
};
