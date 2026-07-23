/** @vitest-environment node */
import { describe, expect, it } from "vitest";
import { buildPMHSchemaIndex } from "./schema";
import { pmhReducer } from "./state";
import { compilePMHSubmission } from "./payload";
import type { PMHSchema } from "./types";

const sampleSchema: PMHSchema = [
  {
    category_id: "cat_cardio",
    farsi_title: "۱. قلب و عروق",
    master_patient_text: "آیا سابقه بیماری قلبی دارید؟",
    questions: [
      {
        id: "pmh_cardio_cad_001",
        category: "Cardiology",
        subcategory: "CAD",
        priority: 1,
        ui_type: "checkbox",
        patient_text: "سکته قلبی؟",
        physician_metadata: { concept: "CAD" },
        conditional_followups: [
          {
            id: "pmh_cardio_cad_001_date",
            ui_type: "text_input",
            patient_text: "کِی؟",
            physician_metadata: "Date of Event",
          },
        ],
      },
    ],
  },
  {
    category_id: "cat_pulm",
    farsi_title: "۲. ریه",
    master_patient_text: "آیا سابقه بیماری ریوی دارید؟",
    questions: [
      {
        id: "pmh_pulm_asthma_001",
        category: "Pulmonology",
        subcategory: "Asthma",
        priority: 1,
        ui_type: "checkbox",
        patient_text: "آسم؟",
        physician_metadata: { concept: "Asthma" },
        conditional_followups: [],
      },
    ],
  },
];

describe("pmhReducer sanitation", () => {
  const index = buildPMHSchemaIndex(sampleSchema);

  it("clears followup values when primary question is toggled off", () => {
    let state = pmhReducer(
      { selectedPrimary: {}, followupValues: {} },
      { type: "toggle_primary", questionId: "pmh_cardio_cad_001", value: true },
      index,
    );

    state = pmhReducer(
      state,
      { type: "set_followup", followupId: "pmh_cardio_cad_001_date", value: "1398" },
      index,
    );

    expect(state.followupValues["pmh_cardio_cad_001_date"]).toBe("1398");

    state = pmhReducer(
      state,
      { type: "toggle_primary", questionId: "pmh_cardio_cad_001", value: false },
      index,
    );

    expect(state.selectedPrimary["pmh_cardio_cad_001"]).toBe(false);
    expect(state.followupValues["pmh_cardio_cad_001_date"]).toBeUndefined();
  });

  it("ignores followup writes when parent primary is not selected", () => {
    const state = pmhReducer(
      { selectedPrimary: {}, followupValues: {} },
      { type: "set_followup", followupId: "pmh_cardio_cad_001_date", value: "1398" },
      index,
    );

    expect(state.followupValues).toEqual({});
  });

  it("strips orphaned followups on hydrate", () => {
    const state = pmhReducer(
      { selectedPrimary: {}, followupValues: {} },
      {
        type: "hydrate",
        state: {
          selectedPrimary: {},
          followupValues: { pmh_cardio_cad_001_date: "1398" },
        },
      },
      index,
    );

    expect(state.followupValues).toEqual({});
  });
});

describe("compilePMHSubmission", () => {
  it("matches backend PMHSubmission shape", () => {
    const index = buildPMHSchemaIndex(sampleSchema);
    const state = pmhReducer(
      { selectedPrimary: {}, followupValues: {} },
      { type: "toggle_primary", questionId: "pmh_cardio_cad_001", value: true },
      index,
    );
    const withFollowup = pmhReducer(
      state,
      { type: "set_followup", followupId: "pmh_cardio_cad_001_date", value: "1398" },
      index,
    );

    const payload = compilePMHSubmission({
      patientId: 123,
      schema: sampleSchema,
      state: withFollowup,
    });

    expect(payload).toEqual({
      patient_id: 123,
      answers: [
        {
          category_id: "cat_cardio",
          is_selected: true,
          question_responses: {
            pmh_cardio_cad_001: true,
            pmh_cardio_cad_001_date: "1398",
          },
        },
        {
          category_id: "cat_pulm",
          is_selected: false,
          question_responses: {},
        },
      ],
    });
  });

  it("omits followups from payload when primary is deselected", () => {
    const index = buildPMHSchemaIndex(sampleSchema);
    let state = pmhReducer(
      { selectedPrimary: {}, followupValues: {} },
      { type: "toggle_primary", questionId: "pmh_cardio_cad_001", value: true },
      index,
    );
    state = pmhReducer(
      state,
      { type: "set_followup", followupId: "pmh_cardio_cad_001_date", value: "1398" },
      index,
    );
    state = pmhReducer(
      state,
      { type: "toggle_primary", questionId: "pmh_cardio_cad_001", value: false },
      index,
    );

    const payload = compilePMHSubmission({
      patientId: 123,
      schema: sampleSchema,
      state,
    });

    const cardio = payload.answers.find((a) => a.category_id === "cat_cardio");
    expect(cardio?.is_selected).toBe(false);
    expect(cardio?.question_responses).toEqual({});
  });
});
