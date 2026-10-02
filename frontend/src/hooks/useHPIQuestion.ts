"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useSaveLayer2Answer } from "./useIntakeHooks";
import type { HPIQuestion, HPIQuestions, IntakeData } from "../../lib/intake";
import { intakeQueryKeys } from "./useIntakeHooks";

export function useHPIQuestion(sessionId: string) {
  const queryClient = useQueryClient();
  const saveAnswerMutation = useSaveLayer2Answer(sessionId);

  // Get fresh data from query cache to avoid stale closures
  const getCurrentIntakeData = (): IntakeData | undefined => {
    return queryClient.getQueryData<IntakeData>(
      intakeQueryKeys.detail(sessionId)
    );
  };

  const getCurrentQuestions = (): HPIQuestions | null | undefined => {
    const intakeData = getCurrentIntakeData();
    return intakeData?.hpi_questions;
  };

  const getCurrentAnswers = (): Record<string, string> | null | undefined => {
    const intakeData = getCurrentIntakeData();
    return intakeData?.hpi_answers;
  };

  const getCurrentQuestionIndex = (): number => {
    const answers = getCurrentAnswers();
    const questions = getCurrentQuestions();
    if (!questions) return 0;
    return answers ? Object.keys(answers).length : 0;
  };

  const getCurrentQuestion = (): HPIQuestion | null => {
    const index = getCurrentQuestionIndex();
    const questions = getCurrentQuestions();
    if (!questions || index >= questions.questions.length) return null;
    return questions.questions[index];
  };

  const saveAnswer = async (questionId: string, answer: string) => {
    await saveAnswerMutation.mutateAsync({ question_id: questionId, answer });
  };

  return {
    getCurrentQuestion,
    getCurrentQuestionIndex,
    getCurrentQuestions,
    getCurrentAnswers,
    saveAnswer,
    isSaving: saveAnswerMutation.isPending,
    error: saveAnswerMutation.error,
  };
}
