import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SoapCitationText from "./SoapCitationText";

const citations = [
  {
    index: 1,
    marker: "[1]",
    source_title: "Harrison's Internal Medicine",
    source_excerpt: "Acute coronary syndrome may present with substernal chest pain.",
    verified: true,
    similarity_score: 0.91,
  },
  {
    index: 2,
    marker: "[2]",
    source_title: "Unsupported Blog",
    source_excerpt: "Unrelated wellness tip.",
    verified: false,
    similarity_score: 0.12,
  },
];

describe("SoapCitationText", () => {
  it("renders citation markers as interactive buttons", () => {
    render(
      <SoapCitationText
        text="Assessment supports ACS [1] and also cites yoga [2]."
        citations={citations}
      />,
    );

    expect(screen.getByRole("button", { name: "ارجاع 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ارجاع تأییدنشده 2" })).toBeInTheDocument();
  });

  it("shows source title and excerpt in popover on hover", async () => {
    const user = userEvent.setup();
    render(
      <SoapCitationText
        text="Assessment supports ACS [1]."
        citations={citations}
      />,
    );

    await user.hover(screen.getByRole("button", { name: "ارجاع 1" }));

    expect(await screen.findByRole("tooltip")).toBeInTheDocument();
    expect(screen.getByText("Harrison's Internal Medicine")).toBeInTheDocument();
    expect(
      screen.getByText("Acute coronary syndrome may present with substernal chest pain."),
    ).toBeInTheDocument();
  });

  it("marks unverified citations with a warning indicator", async () => {
    const user = userEvent.setup();
    render(
      <SoapCitationText text="Yoga claim [2]." citations={citations} />,
    );

    const unverified = screen.getByRole("button", { name: "ارجاع تأییدنشده 2" });
    expect(unverified.className).toContain("bg-amber-100");

    await user.hover(unverified);
    expect(await screen.findByRole("tooltip")).toBeInTheDocument();
    expect(screen.getByText("نیاز به بررسی دستی پزشک")).toBeInTheDocument();
    expect(screen.getByText("Unsupported Blog")).toBeInTheDocument();
  });

  it("does not treat ICD-10 brackets as citation markers", () => {
    render(
      <SoapCitationText
        text="Diagnosis [ICD-10: I21.9] acute MI"
        citations={citations}
      />,
    );

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByText(/ICD-10: I21.9/)).toBeInTheDocument();
  });
});
