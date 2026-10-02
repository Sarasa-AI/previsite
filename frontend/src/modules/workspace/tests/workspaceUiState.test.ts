import { describe, expect, it } from "vitest";
import { deriveWorkspaceUiState } from "../presentation/state/workspaceUiState";

describe("deriveWorkspaceUiState", () => {
  it("returns Idle before fetch", () => {
    expect(deriveWorkspaceUiState({ isIdle: true, hasPlan: false })).toBe("Idle");
  });

  it("returns Loading for transport and wire loading", () => {
    expect(deriveWorkspaceUiState({ hasPlan: false })).toBe("Loading");
    expect(
      deriveWorkspaceUiState({ hasPlan: true, workspaceState: "loading" }),
    ).toBe("Loading");
  });

  it("returns Generating for wire generating and never treats it as Error", () => {
    expect(
      deriveWorkspaceUiState({ hasPlan: true, workspaceState: "generating" }),
    ).toBe("Generating");
  });

  it("maps interactive wire states to Ready", () => {
    for (const workspaceState of [
      "verified",
      "partially_verified",
      "conflict_present",
      "review_needed",
      "completed",
    ]) {
      expect(deriveWorkspaceUiState({ hasPlan: true, workspaceState })).toBe("Ready");
    }
  });

  it("returns Refreshing while refetching with a plan", () => {
    expect(
      deriveWorkspaceUiState({
        hasPlan: true,
        workspaceState: "verified",
        isRefreshing: true,
      }),
    ).toBe("Refreshing");
  });

  it("returns ReadOnly and Offline from wire/client", () => {
    expect(
      deriveWorkspaceUiState({ hasPlan: true, workspaceState: "read_only" }),
    ).toBe("ReadOnly");
    expect(
      deriveWorkspaceUiState({ hasPlan: true, workspaceState: "offline" }),
    ).toBe("Offline");
    expect(deriveWorkspaceUiState({ hasPlan: false, clientOffline: true })).toBe("Offline");
  });

  it("surfaces Forbidden NotFound Error from mapped errors", () => {
    expect(
      deriveWorkspaceUiState({ hasPlan: false, errorUiState: "Forbidden" }),
    ).toBe("Forbidden");
    expect(
      deriveWorkspaceUiState({ hasPlan: false, errorUiState: "NotFound" }),
    ).toBe("NotFound");
    expect(deriveWorkspaceUiState({ hasPlan: false, errorUiState: "Error" })).toBe("Error");
  });
});
