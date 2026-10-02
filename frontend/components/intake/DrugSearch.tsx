"use client";

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Loader2, Search } from "lucide-react";
import { AxiosError } from "axios";
import { extractApiError } from "@/lib/api";
import { frontendApi, type MedicationSearchResult } from "@/lib/client";

type DrugSearchProps = {
  selectedCatalogIds: ReadonlySet<number>;
  selectedNames: ReadonlySet<string>;
  onSelect: (medication: MedicationSearchResult) => void;
  disabled?: boolean;
};

export function DrugSearch({ selectedCatalogIds, selectedNames, onSelect, disabled }: DrugSearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MedicationSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const requestSequence = useRef(0);

  const runSearch = useCallback(async (value: string) => {
    const normalizedQuery = value.trim();
    if (normalizedQuery.length < 2) {
      return;
    }

    const sequence = ++requestSequence.current;
    setLoading(true);
    setError("");
    try {
      const response = await frontendApi.searchMedications(normalizedQuery);
      if (sequence !== requestSequence.current) return;
      setResults(response.data.results.slice(0, 10));
      setSearched(true);
      setHighlightedIndex(response.data.results.length ? 0 : -1);
    } catch (requestError) {
      if (sequence !== requestSequence.current) return;
      const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
      setResults([]);
      setSearched(true);
      setError(
        payload
          ? extractApiError(payload, "جستجوی دارو در حال حاضر در دسترس نیست.")
          : requestError instanceof Error
          ? requestError.message
          : extractApiError(payload, "جستجوی دارو در حال حاضر در دسترس نیست."),
      );
    } finally {
      if (sequence === requestSequence.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const normalizedQuery = query.trim();
    requestSequence.current += 1;
    setError("");
    setSearched(false);
    setHighlightedIndex(-1);
    if (normalizedQuery.length < 2) {
      setResults([]);
      setLoading(false);
      return;
    }

    const timer = window.setTimeout(() => void runSearch(normalizedQuery), 350);
    return () => window.clearTimeout(timer);
  }, [query, runSearch]);

  const selectResult = (result: MedicationSearchResult) => {
    onSelect(result);
    setQuery("");
    setResults([]);
    setSearched(false);
    setHighlightedIndex(-1);
  };

  const handleSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!results.length) return;
      setHighlightedIndex((current) =>
        event.key === "ArrowDown"
          ? (current + 1) % results.length
          : (current - 1 + results.length) % results.length,
      );
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (highlightedIndex >= 0 && results[highlightedIndex]) {
        selectResult(results[highlightedIndex]);
      } else if (!loading && query.trim().length >= 2) {
        // Keep an explicit fallback for users who press Enter before the
        // debounce completes; once suggestions exist, Enter always selects.
        void runSearch(query);
      }
    } else if (event.key === "Escape") {
      event.preventDefault();
      setResults([]);
      setHighlightedIndex(-1);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2" role="search">
        <input
          type="search"
          className="field-input min-w-0 flex-1"
          dir="auto"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={handleSearchKeyDown}
          placeholder="نام فارسی یا انگلیسی دارو"
          aria-label="جستجوی دارو"
          aria-autocomplete="list"
          aria-expanded={results.length > 0}
          aria-controls="medication-suggestions"
          aria-activedescendant={highlightedIndex >= 0 ? `medication-suggestion-${results[highlightedIndex]?.id}` : undefined}
          disabled={disabled}
        />
        <button
          type="button"
          onClick={() => void runSearch(query)}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-trust/30 text-trust transition-colors hover:bg-trust/5"
          aria-label="جستجو"
          disabled={disabled || loading || query.trim().length < 2}
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
        </button>
      </div>

      {error ? <p className="text-sm text-red-600" role="alert">{error}</p> : null}
      {loading && query.trim().length >= 2 ? (
        <div className="flex items-center gap-2 text-sm text-slate-500" role="status">
          <Loader2 className="h-4 w-4 animate-spin" /> در حال جستجو...
        </div>
      ) : null}
      {searched && !loading && results.length === 0 && !error ? (
        <p className="text-sm text-slate-500" role="status">دارویی با این عبارت پیدا نشد.</p>
      ) : null}
      {results.length > 0 ? (
        <ul
          className="max-h-56 divide-y divide-slate-100 overflow-y-auto border-y border-slate-100"
          id="medication-suggestions"
          role="listbox"
          dir="rtl"
          aria-label="پیشنهادهای دارو"
        >
          {results.map((result) => {
            const selected =
              selectedCatalogIds.has(result.id) ||
              selectedNames.has(result.display_name.trim().toLocaleLowerCase());
            return (
              <li id={`medication-suggestion-${result.id}`} key={result.id} role="option" aria-selected={results[highlightedIndex]?.id === result.id}>
                <button
                  type="button"
                  onClick={() => selectResult(result)}
                  onMouseEnter={() => setHighlightedIndex(results.findIndex((item) => item.id === result.id))}
                  className={`w-full px-2 py-2 text-start text-sm transition-colors hover:bg-slate-50 disabled:cursor-default disabled:text-slate-400 ${results[highlightedIndex]?.id === result.id ? "bg-slate-50" : ""}`}
                  disabled={disabled || selected}
                >
                  <span className="block font-semibold text-slate-900">
                    {selected ? `✓ ${result.display_name}` : result.display_name}
                  </span>
                  {result.generic_name_en ? (
                    <span className="block text-xs text-slate-600" dir="auto">
                      {result.generic_name_en}
                    </span>
                  ) : null}
                  {result.strength || result.form ? (
                    <span className="block text-xs text-slate-500" dir="auto">
                      {[result.strength, result.form].filter(Boolean).join(" · ")}
                    </span>
                  ) : null}
                  {result.manufacturer ? (
                    <span className="block text-xs text-slate-400" dir="auto">
                      سازنده: {result.manufacturer}
                    </span>
                  ) : null}
                  {result.company_name ? (
                    <span className="block text-xs text-slate-400" dir="auto">
                      شرکت: {result.company_name}
                    </span>
                  ) : null}
                  {selected ? <span className="block text-xs">قبلاً انتخاب شده</span> : null}
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
