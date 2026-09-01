import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { frontendApi, type MedicationSearchResult } from "@/lib/client";
import { DrugSearch } from "./DrugSearch";

vi.mock("@/lib/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/client")>();
  return {
    ...actual,
    frontendApi: { ...actual.frontendApi, searchMedications: vi.fn() },
  };
});

const result: MedicationSearchResult = {
  id: 101,
  display_name: "Glucophage",
  brand_name_fa: "گلوکوفاژ",
  brand_name_en: "Glucophage",
  generic_name_en: "Metformin",
  form: "TAB",
  strength: "500 mg",
  manufacturer: "Merck",
  dose_unit: "قرص",
};

describe("DrugSearch", () => {
  beforeEach(() => {
    vi.mocked(frontendApi.searchMedications).mockReset();
  });

  it("searches Persian or English text and returns the selected canonical result", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    vi.mocked(frontendApi.searchMedications).mockResolvedValue({ data: { query: "Metformin", results: [result] } } as never);

    render(
      <DrugSearch
        selectedCatalogIds={new Set()}
        selectedNames={new Set()}
        onSelect={onSelect}
      />,
    );
    await user.type(screen.getByLabelText("جستجوی دارو"), "Metformin");
    await user.click(screen.getByRole("button", { name: "جستجو" }));
    await user.click(await screen.findByRole("button", { name: /Glucophage/ }));

    expect(frontendApi.searchMedications).toHaveBeenCalledWith("Metformin");
    expect(onSelect).toHaveBeenCalledWith(result);
  });

  it("searches on Enter without submitting the surrounding form", async () => {
    const user = userEvent.setup();
    vi.mocked(frontendApi.searchMedications).mockResolvedValue({ data: { query: "متفورمین", results: [result] } } as never);

    const outerOnSubmit = vi.fn();
    render(
      <form onSubmit={outerOnSubmit}>
        <DrugSearch
          selectedCatalogIds={new Set()}
          selectedNames={new Set()}
          onSelect={vi.fn()}
        />
      </form>,
    );
    const input = screen.getByLabelText("جستجوی دارو");
    await user.type(input, "متفورمین{enter}");

    expect(frontendApi.searchMedications).toHaveBeenCalledWith("متفورمین");
    expect(outerOnSubmit).not.toHaveBeenCalled();
    expect(await screen.findByRole("button", { name: /Glucophage/ })).toBeInTheDocument();
  });

  it("disables a result already selected by catalog id", async () => {
    const user = userEvent.setup();
    vi.mocked(frontendApi.searchMedications).mockResolvedValue({ data: { query: "متفورمین", results: [result] } } as never);

    render(
      <DrugSearch
        selectedCatalogIds={new Set([101])}
        selectedNames={new Set()}
        onSelect={vi.fn()}
      />,
    );
    await user.type(screen.getByLabelText("جستجوی دارو"), "متفورمین");
    await user.click(screen.getByRole("button", { name: "جستجو" }));

    const selectedResult = await screen.findByRole("button", { name: /قبلاً انتخاب شده/ });
    expect(selectedResult).toBeDisabled();
  });

  it("shows the explicit catalog-unavailable error", async () => {
    const user = userEvent.setup();
    vi.mocked(frontendApi.searchMedications).mockRejectedValue(
      new Error("Darooyab catalog is unavailable"),
    );

    render(
      <DrugSearch
        selectedCatalogIds={new Set()}
        selectedNames={new Set()}
        onSelect={vi.fn()}
      />,
    );
    await user.type(screen.getByLabelText("جستجوی دارو"), "metformin");
    await user.click(screen.getByRole("button", { name: "جستجو" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Darooyab catalog is unavailable",
    );
  });

  it("renders labeled catalog metadata so candidates are distinguishable", async () => {
    const user = userEvent.setup();
    vi.mocked(frontendApi.searchMedications).mockResolvedValue({
      data: { query: "متفورمین ۵۰۰", results: [result] },
    } as never);

    render(
      <DrugSearch
        selectedCatalogIds={new Set()}
        selectedNames={new Set()}
        onSelect={vi.fn()}
      />,
    );
    await user.type(screen.getByLabelText("جستجوی دارو"), "متفورمین ۵۰۰");
    await user.click(screen.getByRole("button", { name: "جستجو" }));

    const card = await screen.findByRole("button", { name: /Glucophage/ });
    expect(card).toHaveTextContent("Metformin");
    expect(card).toHaveTextContent("500 mg · TAB");
    expect(card).toHaveTextContent("سازنده: Merck");
  });
});
