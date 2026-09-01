import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SoapPreviewCard } from "../cards/SoapPreviewCard";
import { soapFixture, trustFixture } from "./fixtures";

describe("SOAP physician workflow safety", () => {
  it("marks contract content as AI draft requiring review", () => {
    render(<SoapPreviewCard content={soapFixture} provenance={trustFixture} />);

    expect(screen.getByText("تولیدشده با AI")).toBeInTheDocument();
    expect(screen.getByText("پیش‌نویس")).toBeInTheDocument();
    expect(screen.getByText("نیازمند بازبینی")).toBeInTheDocument();
    expect(screen.getByText(/نوشته یا تایید پزشک محسوب نمی‌شود/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm SOAP" })).toBeDisabled();
    expect(screen.getByText(/تایید در قرارداد فعلی پشتیبانی نمی‌شود/)).toBeInTheDocument();
  });

  it("keeps review distinct from editing and confirmation", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<SoapPreviewCard content={soapFixture} onConfirm={onConfirm} />);

    await user.click(screen.getByRole("button", { name: "بازبینی" }));
    expect(screen.getByText("در حال بازبینی")).toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "ویرایش" }));
    const assessment = screen.getByLabelText("Edit Assessment / ارزیابی");
    await user.clear(assessment);
    await user.type(assessment, "Edited locally");
    expect(screen.getByText("ویرایش‌شده؛ ذخیره نشده")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm SOAP" })).toBeDisabled();
    expect(onConfirm).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "بازنشانی" }));
    expect(assessment).toHaveValue(soapFixture.assessment);
    expect(screen.queryByText("ویرایش‌شده؛ ذخیره نشده")).not.toBeInTheDocument();
  });

  it("requires a second explicit action before contract-backed confirmation", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<SoapPreviewCard content={soapFixture} onConfirm={onConfirm} />);

    await user.click(screen.getByRole("button", { name: "Confirm SOAP" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Explicitly confirm SOAP" }));
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(onConfirm).toHaveBeenCalledWith(soapFixture);
  });

  it("does not confirm when the confirmation dialog is cancelled", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<SoapPreviewCard content={soapFixture} onConfirm={onConfirm} />);

    await user.click(screen.getByRole("button", { name: "Confirm SOAP" }));
    await user.click(screen.getByRole("button", { name: "انصراف" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("shows confirmed content only from an explicit contract-backed state", () => {
    render(<SoapPreviewCard content={soapFixture} confirmed />);

    expect(screen.getByText("تاییدشده توسط پزشک")).toBeInTheDocument();
    expect(screen.queryByText("تولیدشده با AI")).not.toBeInTheDocument();
    expect(screen.queryByText("نیازمند بازبینی")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ویرایش" })).toBeDisabled();
  });

  it("discloses provenance and explicit missing timestamp", async () => {
    const user = userEvent.setup();
    render(<SoapPreviewCard content={soapFixture} provenance={trustFixture} />);

    await user.click(screen.getByText("منشأ و شواهد"));
    expect(screen.getByLabelText("Provenance for SOAP draft")).toBeInTheDocument();
    expect(screen.getByText("ehr")).toBeInTheDocument();
    expect(screen.getByText("ev-1")).toBeInTheDocument();
    expect(screen.getByText("نامشخص")).toHaveAttribute("data-semantic-state", "unknown");
  });

  it("renders explicit loading, error, unavailable, empty and stale states", () => {
    const { rerender } = render(<SoapPreviewCard content={null} state="loading" />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
    rerender(<SoapPreviewCard content={null} state="error" />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    rerender(<SoapPreviewCard content={null} state="unavailable" />);
    expect(screen.getByText("SOAP در دسترس نیست")).toBeInTheDocument();
    rerender(<SoapPreviewCard content={null} />);
    expect(screen.getByText("پیش‌نویس SOAP موجود نیست")).toBeInTheDocument();
    rerender(<SoapPreviewCard content={soapFixture} state="stale" />);
    expect(screen.getByText("قدیمی")).toBeInTheDocument();
  });

  it("preserves RTL container ownership and bidi clinical text", () => {
    const { container } = render(<SoapPreviewCard content={soapFixture} />);
    expect(container.querySelector("[dir='auto']")).toBeInTheDocument();
    expect(screen.getByLabelText("SOAP draft")).toBeInTheDocument();
  });
});
