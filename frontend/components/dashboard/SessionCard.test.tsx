import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import SessionCard from "./SessionCard";

const baseSession = {
  id: 42,
  initial_complaint: "سردرد",
  created_at: "2026-01-15T10:00:00Z",
  status: "in_progress",
  progress: 40,
};

describe("SessionCard", () => {
  it("renders session id and complaint", () => {
    render(<SessionCard session={baseSession} />);
    expect(screen.getByText("جلسه #42")).toBeInTheDocument();
    expect(screen.getByText("سردرد")).toBeInTheDocument();
  });

  it("shows pending_review amber status label", () => {
    render(
      <SessionCard
        session={{ ...baseSession, status: "pending_review", progress: 80 }}
      />,
    );
    expect(screen.getByText("در انتظار بررسی پزشک")).toBeInTheDocument();
  });

  it("forces circular progress to 100% for pending_review", () => {
    render(
      <SessionCard
        session={{ ...baseSession, status: "pending_review", progress: 55 }}
      />,
    );
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("shows completed status", () => {
    render(<SessionCard session={{ ...baseSession, status: "completed" }} />);
    expect(screen.getByText("تکمیل شده")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("shows in-progress status with given progress", () => {
    render(<SessionCard session={{ ...baseSession, status: "in_progress", progress: 40 }} />);
    expect(screen.getByText("در حال انجام")).toBeInTheDocument();
    expect(screen.getByText("40%")).toBeInTheDocument();
  });

  it("links to intake, upload, and summary", () => {
    render(<SessionCard session={baseSession} />);
    expect(screen.getByRole("link", { name: /ادامه مصاحبه/ })).toHaveAttribute(
      "href",
      "/intake/42",
    );
    expect(screen.getByRole("link", { name: /آپلود فایل/ })).toHaveAttribute(
      "href",
      "/upload/42",
    );
    expect(screen.getByRole("link", { name: /مشاهده خلاصه/ })).toHaveAttribute(
      "href",
      "/summary/42",
    );
  });

  it("shows fallback when complaint is empty", () => {
    render(
      <SessionCard session={{ ...baseSession, initial_complaint: "" }} />,
    );
    expect(
      screen.getByText("شرح اولیه برای این جلسه ثبت نشده است."),
    ).toBeInTheDocument();
  });
});
