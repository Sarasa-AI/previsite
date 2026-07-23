import type { PMHFollowup, PMHQuestion, PMHSchema } from "./types";

export type PMHSchemaIndex = {
  /** questionId -> question */
  questionsById: Map<string, PMHQuestion>;
  /** questionId -> followups (may be empty) */
  followupsByQuestionId: Map<string, PMHFollowup[]>;
  /** followupId -> parent questionId */
  parentQuestionIdByFollowupId: Map<string, string>;
  /** categoryId -> questionIds */
  questionIdsByCategoryId: Map<string, string[]>;
};

export function buildPMHSchemaIndex(schema: PMHSchema): PMHSchemaIndex {
  const questionsById = new Map<string, PMHQuestion>();
  const followupsByQuestionId = new Map<string, PMHFollowup[]>();
  const parentQuestionIdByFollowupId = new Map<string, string>();
  const questionIdsByCategoryId = new Map<string, string[]>();

  for (const category of schema) {
    const questionIds: string[] = [];
    for (const question of category.questions) {
      questionsById.set(question.id, question);
      questionIds.push(question.id);

      const followups = (question.conditional_followups ?? []).filter(Boolean);
      followupsByQuestionId.set(question.id, followups);
      for (const followup of followups) {
        parentQuestionIdByFollowupId.set(followup.id, question.id);
      }
    }
    questionIdsByCategoryId.set(category.category_id, questionIds);
  }

  return {
    questionsById,
    followupsByQuestionId,
    parentQuestionIdByFollowupId,
    questionIdsByCategoryId,
  };
}

