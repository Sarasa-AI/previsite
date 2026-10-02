"use client";

/**
 * Minimal consent screen — structure only.
 *
 * Displays stable placeholder copy keys (e.g. consent.copy.ai_processing.v1).
 * Real medical/legal wording is supplied later; do not invent consent text here.
 */

import { useCallback, useEffect, useState } from "react";
import { AxiosError } from "axios";
import Link from "next/link";
import { AmberBox } from "@/components/patient/amber-box";
import ProtectedRoute from "@/components/ProtectedRoute";
import { BidiText } from "@/components/shared/bidi-text";
import { extractApiError, type ConsentStatusResponse } from "@/lib/api";
import { frontendApi } from "@/lib/client";

export default function PatientConsentPage() {
  const [status, setStatus] = useState<ConsentStatusResponse | null>(null);
  const [error, setError] = useState("");
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const response = await frontendApi.getMyConsents();
      setStatus(response.data);
      setError("");
    } catch (requestError) {
      const payload =
        requestError instanceof AxiosError ? requestError.response?.data : undefined;
      setError(extractApiError(payload, "consent.load_failed"));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const grant = async (consentKey: string) => {
    setBusyKey(consentKey);
    try {
      await frontendApi.grantConsent({ consent_key: consentKey });
      await load();
    } catch (requestError) {
      const payload =
        requestError instanceof AxiosError ? requestError.response?.data : undefined;
      setError(extractApiError(payload, "consent.grant_failed"));
    } finally {
      setBusyKey(null);
    }
  };

  const withdraw = async (consentKey: string) => {
    setBusyKey(consentKey);
    try {
      await frontendApi.withdrawConsent({ consent_key: consentKey });
      await load();
    } catch (requestError) {
      const payload =
        requestError instanceof AxiosError ? requestError.response?.data : undefined;
      setError(extractApiError(payload, "consent.withdraw_failed"));
    } finally {
      setBusyKey(null);
    }
  };

  const requiredMissing =
    status?.consents.filter(
      (c) =>
        status.required_for_processing.includes(c.consent_key) && !c.granted,
    ) ?? [];

  return (
    <ProtectedRoute>
      <main className="space-y-6" dir="rtl">
        <header className="space-y-2">
          <p className="text-sm font-semibold text-primary">
            <BidiText>consent.screen.title</BidiText>
          </p>
          <h1 className="text-2xl font-bold text-slate-900">
            <BidiText>consent.screen.heading</BidiText>
          </h1>
          <p className="text-sm leading-7 text-slate-600">
            <BidiText>consent.screen.intro</BidiText>
          </p>
        </header>

        {status?.enforcement_enabled && requiredMissing.length > 0 ? (
          <AmberBox title="consent.screen.required_notice" live>
            <p>
              <BidiText>consent.screen.missing_keys</BidiText>
              <span aria-hidden="true">: </span>
              <BidiText>
                {requiredMissing.map((c) => c.consent_key).join(", ")}
              </BidiText>
            </p>
          </AmberBox>
        ) : null}

        {error ? (
          <p className="text-sm text-critical" role="alert">
            {error}
          </p>
        ) : null}

        <ul className="space-y-4">
          {(status?.consents ?? []).map((item) => {
            const isRequired = Boolean(
              status?.required_for_processing.includes(item.consent_key),
            );
            return (
              <li
                key={item.consent_key}
                className="space-y-3 rounded-2xl border border-slate-200 p-4"
              >
                <div className="space-y-1">
                  <p className="font-semibold text-slate-900">
                    <BidiText>{item.consent_key}</BidiText>
                    {isRequired ? (
                      <span className="ms-2 text-xs text-warning">
                        <BidiText>consent.screen.required_badge</BidiText>
                      </span>
                    ) : null}
                  </p>
                  {/* Placeholder copy key only — wording supplied later. */}
                  <p className="text-sm text-slate-600">
                    <BidiText>{item.copy_text_key}</BidiText>
                  </p>
                  <p className="text-xs text-slate-500">
                    <BidiText>{item.policy_version}</BidiText>
                    {" · "}
                    <BidiText>
                      {item.granted
                        ? "consent.screen.status.granted"
                        : "consent.screen.status.not_granted"}
                    </BidiText>
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="primary-button"
                    disabled={busyKey === item.consent_key || item.granted}
                    onClick={() => void grant(item.consent_key)}
                    aria-label={`consent.action.grant.${item.consent_key}`}
                  >
                    <BidiText>consent.action.grant</BidiText>
                  </button>
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={busyKey === item.consent_key || !item.granted}
                    onClick={() => void withdraw(item.consent_key)}
                    aria-label={`consent.action.withdraw.${item.consent_key}`}
                  >
                    <BidiText>consent.action.withdraw</BidiText>
                  </button>
                </div>
              </li>
            );
          })}
        </ul>

        <p className="text-sm text-slate-600">
          <Link href="/dashboard" className="text-primary underline">
            <BidiText>consent.screen.back_to_dashboard</BidiText>
          </Link>
        </p>
      </main>
    </ProtectedRoute>
  );
}
