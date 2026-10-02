import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Stable classname helper — migratable with shared primitives. */
export function cx(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
