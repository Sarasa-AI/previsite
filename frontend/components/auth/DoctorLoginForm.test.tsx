import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DoctorLoginForm from "./DoctorLoginForm";

describe("DoctorLoginForm", () => {
  const onSuccess = vi.fn();
  const onMfaRequired = vi.fn();

  beforeEach(() => {
    onSuccess.mockReset();
    onMfaRequired.mockReset();
    vi.restoreAllMocks();
  });

  it("renders username and password fields", () => {
    render(<DoctorLoginForm onSuccess={onSuccess} />);
    expect(screen.getByPlaceholderText("نام کاربری")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("رمز عبور")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "ورود به عنوان پزشک" })).toBeInTheDocument();
  });

  it("shows error for invalid credentials", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        text: async () => JSON.stringify({ detail: "Invalid credentials" }),
      }),
    );

    render(<DoctorLoginForm onSuccess={onSuccess} />);
    await user.type(screen.getByPlaceholderText("نام کاربری"), "bagherzade");
    await user.type(screen.getByPlaceholderText("رمز عبور"), "bad");
    await user.click(screen.getByRole("button", { name: "ورود" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid credentials");
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("shows network error when fetch fails", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    render(<DoctorLoginForm onSuccess={onSuccess} />);
    await user.type(screen.getByPlaceholderText("نام کاربری"), "bagherzade");
    await user.type(screen.getByPlaceholderText("رمز عبور"), "0808");
    await user.click(screen.getByRole("button", { name: "ورود" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "ارتباط با سرور برقرار نشد",
    );
  });

  it("calls onSuccess on successful login without MFA", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        text: async () => JSON.stringify({ access_token: "tok", token_type: "bearer" }),
      }),
    );

    render(<DoctorLoginForm onSuccess={onSuccess} />);
    await user.type(screen.getByPlaceholderText("نام کاربری"), "bagherzade");
    await user.type(screen.getByPlaceholderText("رمز عبور"), "0808");
    await user.click(screen.getByRole("button", { name: "ورود" }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
  });

  it("delegates MFA challenge when mfa_required is returned", async () => {
    const user = userEvent.setup();
    const payload = { mfa_required: true, mfa_token: "challenge" };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        text: async () => JSON.stringify(payload),
      }),
    );

    render(<DoctorLoginForm onSuccess={onSuccess} onMfaRequired={onMfaRequired} />);
    await user.type(screen.getByPlaceholderText("نام کاربری"), "bagherzade");
    await user.type(screen.getByPlaceholderText("رمز عبور"), "0808");
    await user.click(screen.getByRole("button", { name: "ورود" }));

    await waitFor(() => expect(onMfaRequired).toHaveBeenCalledWith(payload));
    expect(onSuccess).not.toHaveBeenCalled();
  });
});
