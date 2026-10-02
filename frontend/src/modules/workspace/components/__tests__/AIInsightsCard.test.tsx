import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AIInsightsCard } from "../ai/AIInsightsCard";
import { projectPlan } from "../../presentation/mappers/projectPlan";
import { makeDirective, makePlan } from "../../tests/fixtures";

function aiPlan(overrides: Parameters<typeof makePlan>[0] = {}) {
  return makePlan({
    layout_directives: [makeDirective({ object_id: "story", slot: "primary", trust: { primary_provenance: "ai_generated", all_provenance: ["ai_generated"], confidence: 0.72, verification: "unverified", evidence_refs: ["ev-story"] } })],
    story: { text: "Review the documented symptom pattern and verify against source evidence.", confidence: 0.72, evidence_refs: ["ev-story"], stale: false },
    ...overrides,
  });
}

describe("AIInsightsCard", () => {
  it("separates AI output from clinical fact and exposes contract metadata", async () => {
    const user = userEvent.setup();
    const vm = projectPlan(aiPlan(), "etag-ai");
    render(<AIInsightsCard viewModel={vm} onRefresh={vi.fn()} />);

    expect(screen.getByLabelText("AI insights")).toBeInTheDocument();
    expect(screen.getByText("تولیدشده با AI")).toHaveAttribute("data-semantic-state", "ai-generated");
    expect(screen.getByText("پیش‌نویس")).toHaveAttribute("data-semantic-state", "draft");
    expect(screen.getByText("نیازمند بازبینی")).toHaveAttribute("data-semantic-state", "warning");
    expect(screen.getByText(/واقعیت بالینی یا تشخیص نیست/)).toBeInTheDocument();
    expect(screen.getAllByText("72٪").length).toBeGreaterThan(0);
    expect(screen.getByText("workspace-orchestrator@1.0.0")).toBeInTheDocument();

    await user.click(screen.getByText("منشأ و شواهد"));
    expect(screen.getByLabelText("Provenance for AI insights")).toBeInTheDocument();
    expect(screen.getByText("ev-story")).toBeInTheDocument();

    await user.click(screen.getByText("پرسش‌های پیشنهادی"));
    expect(screen.getByText("پیشنهادی برای نمایش موجود نیست")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /order/i })).not.toBeInTheDocument();
  });

  it("keeps stale content visible and reviewable", async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();
    const vm = projectPlan(aiPlan({ story: { text: "Stale generated draft", confidence: null, evidence_refs: [], stale: true } }), "etag-stale");
    render(<AIInsightsCard viewModel={vm} onRefresh={onRefresh} />);
    expect(screen.getByText("قدیمی")).toHaveAttribute("data-semantic-state", "stale");
    expect(screen.getByText("ناقص")).toHaveAttribute("data-semantic-state", "unknown");
    expect(screen.getByText("در دسترس نیست")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Refresh AI insights" }));
    expect(onRefresh).toHaveBeenCalledOnce();
  });

  it("renders unavailable, loading and error without creating AI content", () => {
    const missing = projectPlan(aiPlan({ story: null }), "etag-missing");
    const { rerender } = render(<AIInsightsCard viewModel={missing} onRefresh={vi.fn()} />);
    expect(screen.getByText("بینش هوش مصنوعی در دسترس نیست")).toBeInTheDocument();

    rerender(<AIInsightsCard viewModel={missing} uiState="Generating" onRefresh={vi.fn()} />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");

    rerender(<AIInsightsCard viewModel={missing} error={{ code: "WORKSPACE_COMPUTE_FAILED", httpStatus: 500, presentation: "retryable_error" }} onRefresh={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("تولید بینش هوش مصنوعی ناموفق بود");
    expect(screen.queryByText(/Review the documented/)).not.toBeInTheDocument();
  });
});
