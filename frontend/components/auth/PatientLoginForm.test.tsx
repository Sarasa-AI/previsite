import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PatientLoginForm from "./PatientLoginForm";
import { toAsciiDigits, normalizeIranianMobileClient } from "@/lib/phone";
import { mapOtpError } from "@/lib/otp-errors";

describe("phone digit conversion", () => {
  it("converts Persian and Arabic-Indic digits", () => {
    expect(toAsciiDigits("۰۹۱۲")).toBe("0912");
    expect(toAsciiDigits("٠٩١٢")).toBe("0912");
  });

  it("normalizes common Iranian mobile forms", () => {
    expect(normalizeIranianMobileClient("09121234567")).toBe("+989121234567");
    expect(normalizeIranianMobileClient("9121234567")).toBe("+989121234567");
  });
});

describe("mapOtpError", () => {
  it("maps structured codes to Persian messages", () => {
    expect(mapOtpError("INVALID_OTP", "x")).toContain("صحیح نیست");
    expect(mapOtpError("OTP_COOLDOWN", "x")).toContain("صبر");
    expect(mapOtpError("UNKNOWN", "fallback")).toBe("fallback");
  });
});

describe("PatientLoginForm OTP", () => {
  const onSuccess = vi.fn();

  beforeEach(() => {
    onSuccess.mockReset();
    vi.restoreAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders phone step then advances to code step", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        text: async () =>
          JSON.stringify({ success: true, cooldown_seconds: 60, expires_in: 120 }),
      }),
    );

    render(<PatientLoginForm onSuccess={onSuccess} />);
    expect(screen.getByLabelText("شماره موبایل")).toBeInTheDocument();
    await user.type(screen.getByLabelText("شماره موبایل"), "09121234567");
    await user.click(screen.getByRole("button", { name: "دریافت کد" }));

    expect(await screen.findByLabelText("کد تأیید")).toBeInTheDocument();
    expect(screen.getByText(/ارسال مجدد تا/)).toBeInTheDocument();
  });

  it("shows mapped OTP error on verify failure", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        text: async () =>
          JSON.stringify({ success: true, cooldown_seconds: 60, expires_in: 120 }),
      })
      .mockResolvedValueOnce({
        ok: false,
        text: async () => JSON.stringify({ detail: "INVALID_OTP" }),
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<PatientLoginForm onSuccess={onSuccess} />);
    await user.type(screen.getByLabelText("شماره موبایل"), "09121234567");
    await user.click(screen.getByRole("button", { name: "دریافت کد" }));
    await screen.findByLabelText("کد تأیید");
    await user.type(screen.getByLabelText("کد تأیید"), "123456");
    await user.click(screen.getByRole("button", { name: "تأیید و ورود" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("صحیح نیست");
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("counts down resend timer from server cooldown", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        text: async () =>
          JSON.stringify({ success: true, cooldown_seconds: 3, expires_in: 120 }),
      }),
    );

    render(<PatientLoginForm onSuccess={onSuccess} />);
    await user.type(screen.getByLabelText("شماره موبایل"), "09121234567");
    await user.click(screen.getByRole("button", { name: "دریافت کد" }));
    expect(await screen.findByText(/ارسال مجدد تا 3/)).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(3000);
    });
    await waitFor(() => {
      expect(screen.getByText("ارسال مجدد کد")).toBeInTheDocument();
    });
  });
});
