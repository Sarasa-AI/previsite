/** @vitest-environment node */
import { describe, expect, it, vi, beforeEach } from "vitest";

const postMock = vi.fn();
const patchMock = vi.fn();

vi.mock("./api", () => ({
  apiClient: {
    post: (...args: unknown[]) => postMock(...args),
    patch: (...args: unknown[]) => patchMock(...args),
  },
}));

import { frontendApi } from "./client";

describe("frontendApi.uploadFile", () => {
  beforeEach(() => {
    postMock.mockReset();
    postMock.mockResolvedValue({ data: { id: 1 } });
  });

  it("posts FormData including condition fields when caller appended them", async () => {
    const formData = new FormData();
    formData.append("file", new File(["x"], "lab.png", { type: "image/png" }));
    formData.append("condition_id", "cond-abc");
    formData.append("condition_type", "lab");

    await frontendApi.uploadFile("42", formData);

    expect(postMock).toHaveBeenCalledOnce();
    const [url, sentFormData] = postMock.mock.calls[0] as [string, FormData];
    expect(url).toBe("/proxy/api/files/42/upload");
    expect(sentFormData.get("condition_id")).toBe("cond-abc");
    expect(sentFormData.get("condition_type")).toBe("lab");
    expect(sentFormData.get("file")).toBeInstanceOf(File);
  });

  it("posts FormData without condition_type when omitted by caller", async () => {
    const formData = new FormData();
    formData.append("file", new File(["x"], "lab.png", { type: "image/png" }));
    formData.append("condition_id", "cond-abc");

    await frontendApi.uploadFile("42", formData);

    const [, sentFormData] = postMock.mock.calls[0] as [string, FormData];
    expect(sentFormData.get("condition_type")).toBeNull();
  });

  it("posts FormData without condition_id when omitted by caller", async () => {
    const formData = new FormData();
    formData.append("file", new File(["x"], "lab.png", { type: "image/png" }));

    await frontendApi.uploadFile("42", formData);

    const [, sentFormData] = postMock.mock.calls[0] as [string, FormData];
    expect(sentFormData.get("condition_id")).toBeNull();
  });
});

describe("frontendApi.unlinkFile", () => {
  beforeEach(() => {
    patchMock.mockReset();
    patchMock.mockResolvedValue({ data: { id: 7, condition_id: null } });
  });

  it("patches file with condition_id null", async () => {
    await frontendApi.unlinkFile("42", 7);

    expect(patchMock).toHaveBeenCalledWith("/proxy/api/files/42/files/7", {
      condition_id: null,
    });
  });
});
