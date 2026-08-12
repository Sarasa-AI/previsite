/**
 * Architecture boundary isolation — forbidden imports / coupling.
 * Additive source scans only; does not modify production modules.
 */

import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

const MODULE_ROOT = path.resolve(__dirname, "..");

function walkTsFiles(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    if (name === "__tests__" || name === "tests" || name === "stubs") continue;
    const full = path.join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) {
      out.push(...walkTsFiles(full));
    } else if (/\.(ts|tsx)$/.test(name) && !name.endsWith(".test.ts") && !name.endsWith(".test.tsx")) {
      out.push(full);
    }
  }
  return out;
}

function rel(file: string): string {
  return path.relative(MODULE_ROOT, file);
}

describe("Architecture boundaries: forbidden imports", () => {
  const componentFiles = walkTsFiles(path.join(MODULE_ROOT, "components"));

  it("components (Shell, presenters, cards) import no api, application, fetch, React Query, or auth", () => {
    const violations: string[] = [];
    for (const file of componentFiles) {
      const source = readFileSync(file, "utf8");
      const checks: Array<[RegExp, string]> = [
        [/from\s+["'][^"']*\/api(\/|["'])/, "api"],
        [/from\s+["'][^"']*\/application(\/|["'])/, "application"],
        [/\bfetch\s*\(/, "fetch"],
        [/@tanstack\/react-query|react-query|useQuery|useMutation/, "react-query"],
        [/from\s+["'][^"']*auth[^"']*["']/, "auth"],
      ];
      for (const [pattern, label] of checks) {
        if (pattern.test(source)) {
          violations.push(`${rel(file)} → ${label}`);
        }
      }
    }
    expect(violations).toEqual([]);
  });

  it("presenters do not import ClinicalContentViewModel aggregate or mutate props", () => {
    const presentersDir = path.join(MODULE_ROOT, "components", "presenters");
    for (const file of walkTsFiles(presentersDir)) {
      const source = readFileSync(file, "utf8");
      expect(source).not.toMatch(/ClinicalContentViewModel/);
      expect(source).not.toMatch(/from\s+["'][^"']*\/api/);
      expect(source).not.toMatch(/\bfetch\s*\(/);
      expect(source).not.toMatch(/useQuery|@tanstack\/react-query/);
      // Presenters must not mutate props (assignment, not comparison)
      expect(source).not.toMatch(/card\.\w+\s*=(?!=)/);
      expect(source).not.toMatch(/content\.\w+\s*=(?!=)/);
    }
  });

  it("projectPlan may import api/types only — no React, fetch, or hooks", () => {
    const source = readFileSync(
      path.join(MODULE_ROOT, "presentation", "mappers", "projectPlan.ts"),
      "utf8",
    );
    expect(source).toMatch(/from\s+["'].*api\/types["']/);
    expect(source).not.toMatch(/from\s+["']react["']/);
    expect(source).not.toMatch(/\bfetch\s*\(/);
    expect(source).not.toMatch(/useQuery|useMutation|@tanstack\/react-query/);
    expect(source).not.toMatch(/from\s+["'][^"']*\/application/);
  });

  it("projectClinicalContent is pure map — api/types only, no React/fetch/hooks", () => {
    const source = readFileSync(
      path.join(MODULE_ROOT, "presentation", "mappers", "projectClinicalContent.ts"),
      "utf8",
    );
    expect(source).toMatch(/from\s+["'].*api\/types["']/);
    expect(source).not.toMatch(/from\s+["']react["']/);
    expect(source).not.toMatch(/\bfetch\s*\(/);
    expect(source).not.toMatch(/useQuery|useMutation|@tanstack\/react-query/);
    expect(source).not.toMatch(/from\s+["'][^"']*\/application/);
    expect(source).not.toMatch(/ClinicalContext/);
  });

  it("presenters import neither ClinicalContext nor ClinicalContentResponse", () => {
    const presentersDir = path.join(MODULE_ROOT, "components", "presenters");
    for (const file of walkTsFiles(presentersDir)) {
      const source = readFileSync(file, "utf8");
      expect(source).not.toMatch(/ClinicalContext/);
      expect(source).not.toMatch(/ClinicalContentResponse/);
    }
  });

  it("WorkspaceRoute does not compose multiple clinical APIs", () => {
    const source = readFileSync(
      path.join(MODULE_ROOT, "routes", "WorkspaceRoute.tsx"),
      "utf8",
    );
    expect(source).toMatch(/useClinicalContent/);
    expect(source).toMatch(/clinicalContent=/);
    expect(source).not.toMatch(/getIntake|listFiles|summary\(/);
    expect(source).not.toMatch(/clinicalDatasets|GOLDEN_CLINICAL|Fixture/);
  });

  it("useClinicalContent fetches only clinical-content endpoint via workspaceService", () => {
    const source = readFileSync(
      path.join(MODULE_ROOT, "presentation", "hooks", "useClinicalContent.ts"),
      "utf8",
    );
    expect(source).toMatch(/fetchClinicalContent/);
    expect(source).toMatch(/projectClinicalContent/);
    expect(source).not.toMatch(/getIntake|listFiles|\/summary\//);
  });

  it("WorkspaceShell performs composition only — no fetch/hooks/query", () => {
    const source = readFileSync(
      path.join(MODULE_ROOT, "components", "WorkspaceShell.tsx"),
      "utf8",
    );
    expect(source).not.toMatch(/\bfetch\s*\(/);
    expect(source).not.toMatch(/useQuery|useMutation|@tanstack\/react-query/);
    expect(source).not.toMatch(/from\s+["'][^"']*\/api/);
    expect(source).not.toMatch(/from\s+["'][^"']*\/application/);
    // No React hooks in Shell (composition-only)
    expect(source).not.toMatch(/\buse[A-Z]\w*\s*\(/);
  });

  it("registry does not decide visibility, ordering, or priority", () => {
    const source = readFileSync(
      path.join(MODULE_ROOT, "presentation", "registry", "cardRegistry.ts"),
      "utf8",
    );
    // Lookup-only: no runtime assignment of plan chrome fields
    expect(source).not.toMatch(/\bpriority\s*=(?!=)/);
    expect(source).not.toMatch(/\bslot\s*=(?!=)/);
    expect(source).not.toMatch(/\bvisibility_reason\s*=/);
    expect(source).toMatch(/lookup only/i);
    expect(source).toMatch(/Never determines visibility/i);
  });
});
