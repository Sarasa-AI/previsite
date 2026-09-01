"use client";

import { useState, type KeyboardEvent } from "react";
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

  const runSearch = async () => {
    const normalizedQuery = query.trim();
    if (!normalizedQuery || loading) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      const response = await frontendApi.searchMedications(normalizedQuery);
      setResults(response.data.results);
      setSearched(true);
    } catch (requestError) {
      const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
      setResults([]);
      setSearched(false);
      setError(
        requestError instanceof Error
          ? requestError.message
          : extractApiError(payload, "جستجوی دارو در حال حاضر در دسترس نیست."),
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      // This input lives inside the layer-4 form; never let Enter submit that
      // outer form. Trigger the medication search explicitly instead.
      event.preventDefault();
      void runSearch();
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
          disabled={disabled || loading}
        />
        <button
          type="button"
          onClick={() => void runSearch()}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-trust/30 text-trust transition-colors hover:bg-trust/5"
          aria-label="جستجو"
          disabled={disabled || loading || !query.trim()}
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
        </button>
      </div>

      {error ? <p className="text-sm text-red-600" role="alert">{error}</p> : null}
      {searched && results.length === 0 ? (
        <p className="text-sm text-slate-500">دارویی با این عبارت پیدا نشد.</p>
      ) : null}
      {results.length > 0 ? (
        <ul className="max-h-56 divide-y divide-slate-100 overflow-y-auto border-y border-slate-100">
          {results.map((result) => {
            const selected =
              selectedCatalogIds.has(result.id) ||
              selectedNames.has(result.display_name.trim().toLocaleLowerCase());
            return (
              <li key={result.id}>
                <button
                  type="button"
                  className="w-full px-2 py-2 text-start text-sm transition-colors hover:bg-slate-50 disabled:cursor-default disabled:text-slate-400"
                  onClick={() => onSelect(result)}
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
