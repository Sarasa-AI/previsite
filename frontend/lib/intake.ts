export type Demographics = {
  first_name: string;
  last_name: string;
  national_id: string;
  insurance_provider: string;
  age: number;
  sex: string;
  weight: number;
  height: number;
  chief_complaint: string;
};

export type HPIQuestion = {
  id: string;
  question: string;
  priority: number;
  red_flag_related: boolean;
};

export type HPIQuestions = {
  question_strategy: string;
  questions: HPIQuestion[];
};

export type ClinicalSummary = {
  chief_complaint: string;
  hpi_summary: string;
  pertinent_positives: string[];
  pertinent_negatives: string[];
  red_flags: string[];
  patient_questions?: string[];
};

import { normalizeChronicConditions } from "@/lib/pmh/categories";
import type { CurrentMedication, MedicalOverview } from "@/lib/pmh/types";
import { emptyMedicalOverview } from "@/lib/pmh/types";

function normalizeMedication(item: string | CurrentMedication): CurrentMedication {
  if (typeof item === "string") {
    return {
      id: crypto.randomUUID(),
      name: item,
      amount: "",
      frequency: "",
    };
  }

  return {
    id: item.id || crypto.randomUUID(),
    name: item.name ?? "",
    amount: item.amount ?? "",
    frequency: item.frequency ?? "",
  };
}

export type IntakeData = {
  id: number;
  session_id: number;
  current_layer: number;
  session_initial_complaint?: string | null;
  demographics?: Demographics | null;
  hpi_questions?: HPIQuestions | null;
  hpi_answers?: Record<string, string> | null;
  clinical_summary?: ClinicalSummary | null;
  medical_overview?: MedicalOverview | null;
  llm_fallback_used?: boolean;
  llm_error_message?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export function normalizeMedicalOverview(initial?: MedicalOverview | null): MedicalOverview {
  if (!initial) {
    return {
      ...emptyMedicalOverview,
      chronic_conditions: normalizeChronicConditions([]),
    };
  }
  return {
    allergies: initial.allergies ?? "",
    surgical_history: initial.surgical_history ?? "",
    family_history: initial.family_history ?? "",
    chronic_conditions: normalizeChronicConditions(
      initial.chronic_conditions.map((c) => ({
        id: c.id,
        name: c.name,
        duration: c.duration ?? "",
      })),
    ),
    current_medications: (initial.current_medications ?? []).map((medication) =>
      normalizeMedication(medication as string | CurrentMedication),
    ),
    lab_results: (initial.lab_results ?? []).map((lab) => ({
      id: lab.id,
      name: lab.name,
      ...(lab.extracted_data ? { extracted_data: lab.extracted_data } : {}),
    })),
    patient_questions: initial.patient_questions?.trim() || null,
  };
}

export const INSURANCE_PROVIDERS = [
  "تأمین اجتماعی",
  "سلامت",
  "نیروهای مسلح",
  "بیمه تکمیلی",
  "آزاد (بدون بیمه)",
];

export const SEX_OPTIONS = [
  { value: "male", label: "مرد" },
  { value: "female", label: "زن" },
];

