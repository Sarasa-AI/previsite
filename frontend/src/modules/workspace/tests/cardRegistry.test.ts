import { describe, expect, it } from "vitest";
import {
  isRegisteredObjectId,
  listRegisteredObjectIds,
  resolveCardPresenter,
} from "../presentation/registry/cardRegistry";
import { CURRENTLY_SUPPORTED_OBJECT_IDS } from "../presentation/mappers/projectPlan";
import { onWorkspaceTelemetry } from "@/src/shared/utils/telemetry";

describe("cardRegistry", () => {
  it("resolves all currently supported object_ids", () => {
    const registered = listRegisteredObjectIds();
    for (const objectId of CURRENTLY_SUPPORTED_OBJECT_IDS) {
      expect(isRegisteredObjectId(objectId)).toBe(true);
      expect(resolveCardPresenter(objectId)).not.toBeNull();
    }
    expect(registered.length).toBe(CURRENTLY_SUPPORTED_OBJECT_IDS.size);
  });

  it("registry keys and supported IDs stay bidirectionally synchronized", () => {
    const registered = new Set(listRegisteredObjectIds());
    expect(registered).toEqual(CURRENTLY_SUPPORTED_OBJECT_IDS);
    for (const objectId of registered) {
      expect(CURRENTLY_SUPPORTED_OBJECT_IDS.has(objectId)).toBe(true);
    }
    for (const objectId of CURRENTLY_SUPPORTED_OBJECT_IDS) {
      expect(registered.has(objectId)).toBe(true);
    }
  });

  it("each registered presenter is assigned to exactly one object_id (card semantics)", () => {
    const registered = listRegisteredObjectIds();
    const presenters = registered.map((id) => resolveCardPresenter(id));
    // Distinct presenter function references per object_id
    expect(new Set(presenters).size).toBe(registered.length);
    for (const objectId of registered) {
      const Presenter = resolveCardPresenter(objectId);
      expect(Presenter).not.toBeNull();
      expect(Presenter!.name.toLowerCase()).not.toMatch(/stub/);
    }
  });

  it("skips unknown object_id with telemetry and does not throw", () => {
    const events: Array<{ event: string; object_id?: string }> = [];
    const stop = onWorkspaceTelemetry((event, payload) => {
      events.push({ event, object_id: payload.object_id as string | undefined });
    });
    const presenter = resolveCardPresenter("not_a_real_card", {
      sessionId: 42,
      planEtag: "e",
      contractVersion: "1.0.0",
    });
    stop();
    expect(presenter).toBeNull();
    expect(events.some((e) => e.event === "workspace.unknown_object_id" && e.object_id === "not_a_real_card")).toBe(
      true,
    );
  });
});
