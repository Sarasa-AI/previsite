import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WorkspaceShell } from "../WorkspaceShell";
import { projectPlan } from "../../presentation/mappers/projectPlan";
import { makeDirective, makePlan } from "../../tests/fixtures";
import { resolveCardPresenter } from "../../presentation/registry/cardRegistry";
import { listRegisteredObjectIds } from "../../presentation/registry/cardRegistry";
import type { WorkspaceViewModel } from "../../presentation/viewmodels/types";

const noop = vi.fn();

function renderShell(
  overrides: Partial<{
    uiState: Parameters<typeof WorkspaceShell>[0]["uiState"];
    viewModel: WorkspaceViewModel | null;
    error: Parameters<typeof WorkspaceShell>[0]["error"];
  }> = {},
) {
  const plan = makePlan({
    layout_directives: [
      makeDirective({ object_id: "critical_alerts", slot: "pin", priority: "p0", size: "expanded", pinned: true }),
      makeDirective({ object_id: "chief_complaint", slot: "primary", priority: "p1" }),
      makeDirective({ object_id: "red_flags", slot: "primary", priority: "p0" }),
      makeDirective({ object_id: "timeline", slot: "primary", priority: "p1" }),
      makeDirective({ object_id: "labs", slot: "primary", priority: "p1" }),
      makeDirective({ object_id: "medications", slot: "primary", priority: "p2" }),
      makeDirective({ object_id: "missing_data", slot: "secondary", priority: "p2" }),
      makeDirective({ object_id: "soap", slot: "secondary", priority: "p2" }),
      makeDirective({ object_id: "documents", slot: "deferred", priority: "p3", size: "compressed" }),
      makeDirective({ object_id: "snapshot", slot: "secondary", priority: "p2" }),
    ],
    pin_zone: ["critical_alerts"],
  });
  const viewModel = overrides.viewModel === null ? null : overrides.viewModel ?? projectPlan(plan, "etag-test");

  return render(
    <WorkspaceShell
      uiState={overrides.uiState ?? "Ready"}
      viewModel={viewModel}
      error={overrides.error ?? null}
      onAcknowledge={noop}
      onRefreshStory={noop}
      onRetry={noop}
    />,
  );
}

describe("WorkspaceShell assembly", () => {
  it("renders complete workspace with regions and patient header", () => {
    renderShell();
    expect(screen.getByLabelText("Doctor workspace")).toBeInTheDocument();
    expect(screen.getByLabelText("Patient header")).toBeInTheDocument();
    expect(screen.getByLabelText("Pinned")).toBeInTheDocument();
    expect(screen.getByLabelText("Primary")).toBeInTheDocument();
    expect(screen.getByLabelText("Secondary")).toBeInTheDocument();
    expect(screen.getByLabelText("Deferred cards")).toBeInTheDocument();
    expect(screen.getByLabelText("Decision queue")).toBeInTheDocument();
  });

  it("renders pinned cards from registry order", () => {
    const { container } = renderShell();
    const pin = container.querySelector('[data-workspace-band="pin"]');
    expect(pin).toBeTruthy();
    expect(within(pin as HTMLElement).getByLabelText("Critical alerts")).toBeInTheDocument();
  });

  it("renders primary region cards including story", () => {
    const { container } = renderShell();
    const primary = container.querySelector('[data-workspace-band="primary"]');
    expect(primary).toBeTruthy();
    expect(within(primary as HTMLElement).getByLabelText("Clinical story")).toBeInTheDocument();
    expect(within(primary as HTMLElement).getByLabelText("Chief complaint")).toBeInTheDocument();
    expect(within(primary as HTMLElement).getByLabelText("Timeline")).toBeInTheDocument();
    expect(within(primary as HTMLElement).getByLabelText("Labs")).toBeInTheDocument();
    expect(within(primary as HTMLElement).getByLabelText("Medications")).toBeInTheDocument();
  });

  it("renders secondary region cards", () => {
    const { container } = renderShell();
    const secondary = container.querySelector('[data-workspace-band="secondary"]');
    expect(secondary).toBeTruthy();
    expect(within(secondary as HTMLElement).getByLabelText("Missing information")).toBeInTheDocument();
    expect(within(secondary as HTMLElement).getByLabelText("SOAP preview")).toBeInTheDocument();
    expect(within(secondary as HTMLElement).getByLabelText("Clinical snapshot")).toBeInTheDocument();
  });

  it("renders deferred region collapsed by default", () => {
    const { container } = renderShell();
    const deferred = container.querySelector('[data-workspace-band="deferred"]') as HTMLDetailsElement;
    expect(deferred).toBeTruthy();
    expect(deferred.open).toBe(false);
    expect(within(deferred).getByLabelText("Source documents")).toBeInTheDocument();
  });

  it("expands deferred via keyboard-accessible summary", async () => {
    const user = userEvent.setup();
    const { container } = renderShell();
    const deferred = container.querySelector('[data-workspace-band="deferred"]') as HTMLDetailsElement;
    await user.click(screen.getByLabelText("Deferred cards"));
    expect(deferred.open).toBe(true);
  });

  it("renders loading screen with skeletons", () => {
    renderShell({ uiState: "Loading", viewModel: null });
    expect(screen.getByLabelText("Loading doctor workspace")).toBeInTheDocument();
    expect(screen.getByLabelText("Loading patient header")).toBeInTheDocument();
    expect(screen.getByLabelText("Loading chief complaint")).toBeInTheDocument();
  });

  it("renders empty screen when plan missing", () => {
    renderShell({ uiState: "Ready", viewModel: null });
    expect(screen.getByText("No workspace plan")).toBeInTheDocument();
  });

  it("renders error screen with retry", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <WorkspaceShell
        uiState="Error"
        viewModel={null}
        error={{ code: "WORKSPACE_COMPUTE_FAILED", httpStatus: 500, presentation: "retryable_error" }}
        onAcknowledge={noop}
        onRefreshStory={noop}
        onRetry={onRetry}
      />,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("WORKSPACE_COMPUTE_FAILED")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("renders forbidden and not-found states", () => {
    const { rerender } = render(
      <WorkspaceShell
        uiState="Forbidden"
        viewModel={null}
        error={null}
        onAcknowledge={noop}
        onRefreshStory={noop}
        onRetry={noop}
      />,
    );
    expect(screen.getByText("Access denied")).toBeInTheDocument();

    rerender(
      <WorkspaceShell
        uiState="NotFound"
        viewModel={null}
        error={null}
        onAcknowledge={noop}
        onRefreshStory={noop}
        onRetry={noop}
      />,
    );
    expect(screen.getByText("Workspace not found")).toBeInTheDocument();
  });

  it("marks partial generating state", () => {
    const plan = makePlan({ workspace_state: "generating" });
    const viewModel = projectPlan(plan, "etag-gen");
    const { container } = renderShell({ uiState: "Generating", viewModel });
    expect(container.querySelector('[data-partial="true"]')).toBeTruthy();
  });

  it("supports RTL container without horizontal overflow classes", () => {
    const { container } = render(
      <div dir="rtl">
        <WorkspaceShell
          uiState="Ready"
          viewModel={projectPlan(makePlan(), "etag-rtl")}
          error={null}
          onAcknowledge={noop}
          onRefreshStory={noop}
          onRetry={noop}
        />
      </div>,
    );
    expect(container.querySelector("[dir='rtl']")).toBeTruthy();
    expect(container.querySelector(".overflow-x-hidden")).toBeTruthy();
    expect(screen.getByLabelText("Doctor workspace")).toBeInTheDocument();
  });

  it("exposes ARIA landmarks and heading hierarchy", () => {
    renderShell();
    expect(screen.getByRole("main", { name: "Doctor workspace" })).toBeInTheDocument();
    expect(screen.getByRole("banner", { name: "Workspace status" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Clinical story" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Decision queue" })).toBeInTheDocument();
  });

  it("uses responsive layout classes on secondary region", () => {
    const { container } = renderShell();
    const secondary = container.querySelector('[data-workspace-band="secondary"]');
    expect(secondary?.className).toMatch(/md:grid-cols-2/);
    expect(secondary?.className).toMatch(/xl:grid-cols-3/);
  });

  it("composes production presenters via registry (no stubs)", () => {
    for (const objectId of listRegisteredObjectIds()) {
      const Presenter = resolveCardPresenter(objectId);
      expect(Presenter).not.toBeNull();
      expect(Presenter!.name).not.toMatch(/Stub/i);
    }
  });
});

describe("DecisionQueuePanel resolve/dismiss CTAs", () => {
  function queueViewModel(mutationsAllowed: boolean) {
    const plan = makePlan({
      workspace_state: mutationsAllowed ? "review_needed" : "read_only",
      decision_queue: [
        {
          rank: 1,
          object_id: "critical_alerts",
          reason_code: "SAFETY",
          explanation: "Review critical alerts",
          acknowledge_required: true,
        },
      ],
      layout_directives: [
        makeDirective({ object_id: "critical_alerts", slot: "pin", priority: "p0", size: "expanded", pinned: true }),
      ],
      pin_zone: ["critical_alerts"],
    });
    return projectPlan(plan, "etag-queue");
  }

  it("renders Resolve/Dismiss when mutationsAllowed and callbacks provided", () => {
    render(
      <WorkspaceShell
        uiState="Ready"
        viewModel={queueViewModel(true)}
        error={null}
        onAcknowledge={noop}
        onRefreshStory={noop}
        onRetry={noop}
        onResolve={noop}
        onDismiss={noop}
      />,
    );
    expect(screen.getByRole("button", { name: "Acknowledge" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resolve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dismiss" })).toBeInTheDocument();
  });

  it("hides Resolve/Dismiss when mutationsAllowed is false", () => {
    render(
      <WorkspaceShell
        uiState="ReadOnly"
        viewModel={queueViewModel(false)}
        error={null}
        onAcknowledge={noop}
        onRefreshStory={noop}
        onRetry={noop}
        onResolve={noop}
        onDismiss={noop}
      />,
    );
    expect(screen.queryByRole("button", { name: "Resolve" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Dismiss" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Acknowledge" })).not.toBeInTheDocument();
  });

  it("calls onResolve/onDismiss with objectId and disables while pending", async () => {
    const user = userEvent.setup();
    const onResolve = vi.fn();
    const onDismiss = vi.fn();
    const { rerender } = render(
      <WorkspaceShell
        uiState="Ready"
        viewModel={queueViewModel(true)}
        error={null}
        onAcknowledge={noop}
        onRefreshStory={noop}
        onRetry={noop}
        onResolve={onResolve}
        onDismiss={onDismiss}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Resolve" }));
    expect(onResolve).toHaveBeenCalledWith("critical_alerts");

    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onDismiss).toHaveBeenCalledWith("critical_alerts");

    rerender(
      <WorkspaceShell
        uiState="Ready"
        viewModel={queueViewModel(true)}
        error={null}
        onAcknowledge={noop}
        onRefreshStory={noop}
        onRetry={noop}
        onResolve={onResolve}
        onDismiss={onDismiss}
        resolvePending
        dismissPending
      />,
    );
    expect(screen.getByRole("button", { name: "Resolve" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Dismiss" })).toBeDisabled();
  });
});

describe("stub removal regression", () => {
  it("stubs directory no longer exists", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const stubsPath = path.join(__dirname, "../stubs");
    expect(fs.existsSync(stubsPath)).toBe(false);
  });

  it("registry presenters render CardChrome-framed empty content", () => {
    const Presenter = resolveCardPresenter("chief_complaint");
    expect(Presenter).not.toBeNull();
    const Card = Presenter!;
    render(
      <Card
        card={{
          objectId: "chief_complaint",
          priority: "p1",
          slot: "primary",
          size: "standard",
          pinned: false,
          trust: {
            primaryProvenance: "ehr",
            allProvenance: ["ehr"],
            confidence: 0.9,
            verification: "verified",
            evidenceRefs: [],
          },
          flags: [],
        }}
      />,
    );
    expect(screen.getByLabelText("Chief complaint")).toBeInTheDocument();
    expect(screen.getByText("No chief complaint")).toBeInTheDocument();
    expect(screen.getByLabelText(/Trust: verified/i)).toBeInTheDocument();
  });
});
