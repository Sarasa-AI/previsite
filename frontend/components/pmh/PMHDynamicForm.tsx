"use client";

import * as React from "react";
import { useMemo, useReducer } from "react";
import { Stethoscope } from "lucide-react";
import { usePMHSchema } from "@/src/hooks/usePMHSchema";
import type { PMHAnswersState, PMHSchema, PMHSubmission } from "@/lib/pmh/types";
import { emptyPMHAnswersState } from "@/lib/pmh/types";
import { buildPMHSchemaIndex } from "@/lib/pmh/schema";
import { pmhReducer } from "@/lib/pmh/state";
import { compilePMHSubmission } from "@/lib/pmh/payload";
import { PMHCategoryCard } from "./PMHCategoryCard";
import { PMHFollowups } from "./PMHFollowups";
import { PMHQuestionRow } from "./PMHQuestionRow";

type PMHDynamicFormProps = {
  patientId: number;
  /** Called whenever local PMH state changes (parent can compile+submit on final submit). */
  onSubmissionChange?: (submission: PMHSubmission, rawState: PMHAnswersState, schema: PMHSchema) => void;
};

export function PMHDynamicForm({ patientId, onSubmissionChange }: PMHDynamicFormProps) {
  const { data, isLoading, error } = usePMHSchema();

  const schema = data ?? null;
  const schemaIndex = useMemo(() => (schema ? buildPMHSchemaIndex(schema) : null), [schema]);

  const [state, dispatchBase] = useReducer(
    (s: PMHAnswersState, a: Parameters<typeof pmhReducer>[1]) => {
      if (!schemaIndex) return s;
      return pmhReducer(s, a, schemaIndex);
    },
    emptyPMHAnswersState,
  );

  const dispatch = React.useCallback(
    (action: Parameters<typeof pmhReducer>[1]) => dispatchBase(action),
    [dispatchBase],
  );

  const compiled = useMemo(() => {
    if (!schema) return null;
    return compilePMHSubmission({ patientId, schema, state });
  }, [patientId, schema, state]);

  React.useEffect(() => {
    if (!schema || !compiled) return;
    onSubmissionChange?.(compiled, state, schema);
  }, [compiled, onSubmissionChange, schema, state]);

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-600">
        در حال بارگذاری سوالات سوابق پزشکی...
      </div>
    );
  }

  if (error || !schemaIndex || !schema) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-6 text-sm text-red-700">
        بارگذاری فرم سوابق پزشکی ناموفق بود.
      </div>
    );
  }

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2 text-trust">
        <Stethoscope className="h-5 w-5" />
        <h3 className="text-lg font-bold">PMH | سوابق پزشکی گذشته (فرم پویا)</h3>
      </div>

      <div className="space-y-4">
        {schema.map((category, idx) => (
          <PMHCategoryCard
            key={category.category_id}
            title={category.farsi_title}
            prompt={category.master_patient_text}
            defaultOpen={idx === 0}
          >
            {category.questions.map((q) => {
              const checked = Boolean(state.selectedPrimary[q.id]);
              const followups = schemaIndex.followupsByQuestionId.get(q.id) ?? [];
              return (
                <div key={q.id}>
                  <PMHQuestionRow
                    id={q.id}
                    text={q.patient_text}
                    checked={checked}
                    onChange={(value) => dispatch({ type: "toggle_primary", questionId: q.id, value })}
                  />

                  <div
                    className={`transition-[grid-template-rows,opacity,transform] duration-300 ease-out ${
                      checked ? "grid grid-rows-[1fr] opacity-100 translate-y-0" : "grid grid-rows-[0fr] opacity-0 -translate-y-1"
                    }`}
                  >
                    <div className="overflow-hidden">
                      <PMHFollowups
                        followups={followups}
                        values={state.followupValues}
                        onChange={(followupId, value) => dispatch({ type: "set_followup", followupId, value })}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </PMHCategoryCard>
        ))}
      </div>
    </section>
  );
}

