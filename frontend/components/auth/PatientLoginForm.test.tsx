import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PatientLoginForm from "./PatientLoginForm";

describe("PatientLoginForm", () => {
  const onSuccess = vi.fn();

  beforeEach(() => {
    onSuccess.mockReset();
    vi.restoreAllMocks();
  });

  it("renders national id and password fields", () => {
    render(<PatientLoginForm onSuccess={onSuccess} />);
    expect(screen.getByPlaceholderText("کد ملی (۱۰ رقم)")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("رمز عبور")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ورود" })).toBeInTheDocument();
  });

  it("shows API error for invalid credentials", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        text: async () => JSON.stringify({ detail: "Invalid credentials" }),
      }),
    );

    render(<PatientLoginForm onSuccess={onSuccess} />);
    await user.type(screen.getByPlaceholderText("کد ملی (۱۰ رقم)"), "0499370899");
    await user.type(screen.getByPlaceholderText("رمز عبور"), "wrong-pass");
    await user.click(screen.getByRole("button", { name: "ورود" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid credentials");
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("maps USER_EXISTS-style auth detail via mapAuthError fallback path", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        text: async () => JSON.stringify({ detail: "INVALID_NATIONAL_ID" }),
      }),
    );

    render(<PatientLoginForm onSuccess={onSuccess} />);
    await user.type(screen.getByPlaceholderText("کد ملی (۱۰ رقم)"), "1234567890");
    await user.type(screen.getByPlaceholderText("رمز عبور"), "password12");
    await user.click(screen.getByRole("button", { name: "ورود" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "کد ملی وارد شده معتبر نیست",
    );
  });

  it("shows network error when fetch throws", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    render(<PatientLoginForm onSuccess={onSuccess} />);
    await user.type(screen.getByPlaceholderText("کد ملی (۱۰ رقم)"), "0499370899");
    await user.type(screen.getByPlaceholderText("رمز عبور"), "password12");
    await user.click(screen.getByRole("button", { name: "ورود" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "ارتباط با سرور برقرار نشد",
    );
  });

  it("calls onSuccess when login succeeds", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        text: async () => JSON.stringify({ access_token: "tok", token_type: "bearer" }),
      }),
    );

    render(<PatientLoginForm onSuccess={onSuccess} />);
    await user.type(screen.getByPlaceholderText("کد ملی (۱۰ رقم)"), "0499370899");
    await user.type(screen.getByPlaceholderText("رمز عبور"), "VeryStrongPassword123!");
    await user.click(screen.getByRole("button", { name: "ورود" }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
  });
});
