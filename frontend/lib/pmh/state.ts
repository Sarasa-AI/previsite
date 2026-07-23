import type { PMHAnswersState } from "./types";
import type { PMHSchemaIndex } from "./schema";

export type PMHAction =
  | { type: "toggle_primary"; questionId: string; value: boolean }
  | { type: "set_followup"; followupId: string; value: string }
  | { type: "hydrate"; state: PMHAnswersState }
  | { type: "reset" };

export function pmhReducer(
  state: PMHAnswersState,
  action: PMHAction,
  schemaIndex: PMHSchemaIndex,
): PMHAnswersState {
  switch (action.type) {
    case "hydrate": {
      // Trust-but-verify: strip any followup values whose parent question is not selected.
      const next: PMHAnswersState = {
        selectedPrimary: { ...action.state.selectedPrimary },
        followupValues: { ...action.state.followupValues },
      };

      for (const followupId of Object.keys(next.followupValues)) {
        const parentId = schemaIndex.parentQuestionIdByFollowupId.get(followupId);
        if (!parentId || !next.selectedPrimary[parentId]) {
          delete next.followupValues[followupId];
        }
      }
      return next;
    }
    case "reset":
      return { selectedPrimary: {}, followupValues: {} };

    case "toggle_primary": {
      const selectedPrimary = { ...state.selectedPrimary, [action.questionId]: action.value };

      if (action.value) {
        return { ...state, selectedPrimary };
      }

      // Strict sanitation: toggling a primary OFF must delete all child followups immediately.
      const followupValues = { ...state.followupValues };
      const followups = schemaIndex.followupsByQuestionId.get(action.questionId) ?? [];
      for (const followup of followups) {
        delete followupValues[followup.id];
      }

      return { selectedPrimary, followupValues };
    }

    case "set_followup": {
      const parentId = schemaIndex.parentQuestionIdByFollowupId.get(action.followupId);
      if (!parentId || !state.selectedPrimary[parentId]) {
        // Parent is not active; ignore writes for hidden inputs.
        return state;
      }

      const trimmed = action.value;
      const followupValues = { ...state.followupValues };
      if (!trimmed) {
        delete followupValues[action.followupId];
      } else {
        followupValues[action.followupId] = trimmed;
      }
      return { ...state, followupValues };
    }
  }
}

