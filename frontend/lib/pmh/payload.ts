import type { PMHAnswersState, PMHSchema, PMHSubmission } from "./types";
import { buildPMHSchemaIndex } from "./schema";

export function compilePMHSubmission(args: {
  patientId: number;
  schema: PMHSchema;
  state: PMHAnswersState;
}): PMHSubmission {
  const { patientId, schema, state } = args;
  const index = buildPMHSchemaIndex(schema);

  const answers = schema.map((category) => {
    const questionIds = index.questionIdsByCategoryId.get(category.category_id) ?? [];

    const question_responses: Record<string, boolean | string> = {};
    let is_selected = false;

    for (const qid of questionIds) {
      if (state.selectedPrimary[qid]) {
        is_selected = true;
        question_responses[qid] = true;

        const followups = index.followupsByQuestionId.get(qid) ?? [];
        for (const followup of followups) {
          const value = state.followupValues[followup.id];
          if (typeof value === "string" && value.trim()) {
            question_responses[followup.id] = value.trim();
          }
        }
      }
    }

    return {
      category_id: category.category_id,
      is_selected,
      question_responses,
    };
  });

  return {
    patient_id: patientId,
    answers,
  };
}

