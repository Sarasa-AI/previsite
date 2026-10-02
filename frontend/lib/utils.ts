import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Canonical classname helper for UI work — mirrors modules/workspace's `cx`. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
