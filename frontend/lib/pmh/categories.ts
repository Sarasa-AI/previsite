import type { ChronicCondition } from "@/lib/pmh/types";

export type PMHSystemCategory = {
  id: string;
  label: string;
  namePrefix: string;
};

export const PMH_SYSTEM_CATEGORIES: PMHSystemCategory[] = [
  {
    id: "a1000001-0000-4000-8000-000000000001",
    label: "غدد و متابولیسم",
    namePrefix: "غدد",
  },
  {
    id: "a1000001-0000-4000-8000-000000000002",
    label: "قلب و عروق",
    namePrefix: "قلب",
  },
  {
    id: "a1000001-0000-4000-8000-000000000003",
    label: "چشم‌پزشکی",
    namePrefix: "چشم",
  },
  {
    id: "a1000001-0000-4000-8000-000000000004",
    label: "مغز و اعصاب",
    namePrefix: "مغز",
  },
  {
    id: "a1000001-0000-4000-8000-000000000005",
    label: "بیماری‌های کلیوی",
    namePrefix: "کلیه",
  },
  {
    id: "a1000001-0000-4000-8000-000000000006",
    label: "روماتولوژی",
    namePrefix: "روماتولوژی",
  },
  {
    id: "a1000001-0000-4000-8000-000000000007",
    label: "زنان و بارداری",
    namePrefix: "زنان",
  },
];

export const PMH_CATEGORY_BY_ID: Record<string, PMHSystemCategory> = Object.fromEntries(
  PMH_SYSTEM_CATEGORIES.map((category) => [category.id, category]),
);

const SYSTEM_CATEGORY_IDS = new Set(PMH_SYSTEM_CATEGORIES.map((category) => category.id));

export function isSystemCategoryId(id: string): boolean {
  return SYSTEM_CATEGORY_IDS.has(id);
}

export function formatCategoryConditionName(prefix: string, detail: string): string {
  return `${prefix}: ${detail.trim()}`;
}

export function stripCategoryPrefix(name: string, category: PMHSystemCategory): string {
  const prefixed = `${category.namePrefix}:`;
  if (name.startsWith(prefixed)) {
    return name.slice(prefixed.length).trim();
  }
  return name;
}

function findCategoryByNamePrefix(name: string): PMHSystemCategory | undefined {
  return PMH_SYSTEM_CATEGORIES.find((category) => name.startsWith(`${category.namePrefix}:`));
}

export function normalizeChronicConditions(saved: ChronicCondition[]): ChronicCondition[] {
  const consumedIds = new Set<string>();
  const result: ChronicCondition[] = [];

  for (const category of PMH_SYSTEM_CATEGORIES) {
    const byId = saved.find((condition) => condition.id === category.id);
    if (byId) {
      consumedIds.add(byId.id);
      const name = stripCategoryPrefix(byId.name, category).trim();
      if (name) {
        result.push({
          id: category.id,
          name,
          duration: byId.duration ?? "",
        });
      }
      continue;
    }

    const byPrefix = saved.find(
      (condition) =>
        !consumedIds.has(condition.id) && findCategoryByNamePrefix(condition.name)?.id === category.id,
    );
    if (byPrefix) {
      consumedIds.add(byPrefix.id);
      const name = stripCategoryPrefix(byPrefix.name, category).trim();
      if (name) {
        result.push({
          id: category.id,
          name,
          duration: byPrefix.duration ?? "",
        });
      }
    }
  }

  for (const condition of saved) {
    if (consumedIds.has(condition.id) || isSystemCategoryId(condition.id)) {
      continue;
    }
    result.push({
      id: condition.id,
      name: condition.name,
      duration: condition.duration ?? "",
    });
  }

  return result;
}

export function ensureCategorizedConditions(saved: ChronicCondition[]): ChronicCondition[] {
  const savedById = new Map(saved.map((condition) => [condition.id, condition]));
  const consumedIds = new Set<string>();

  const systemRows = PMH_SYSTEM_CATEGORIES.map((category) => {
    const byId = savedById.get(category.id);
    if (byId) {
      consumedIds.add(byId.id);
      return {
        id: category.id,
        name: stripCategoryPrefix(byId.name, category),
        duration: byId.duration ?? "",
      };
    }

    const byPrefix = saved.find(
      (condition) =>
        !consumedIds.has(condition.id) && findCategoryByNamePrefix(condition.name)?.id === category.id,
    );
    if (byPrefix) {
      consumedIds.add(byPrefix.id);
      return {
        id: category.id,
        name: stripCategoryPrefix(byPrefix.name, category),
        duration: byPrefix.duration ?? "",
      };
    }

    return {
      id: category.id,
      name: "",
      duration: "",
    };
  });

  const extraRows = saved
    .filter((condition) => !consumedIds.has(condition.id) && !isSystemCategoryId(condition.id))
    .map((condition) => ({
      id: condition.id,
      name: condition.name,
      duration: condition.duration ?? "",
    }));

  return [...systemRows, ...extraRows];
}
