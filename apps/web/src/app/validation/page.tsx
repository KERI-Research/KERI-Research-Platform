"use client";

import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { RESEARCH_DISCLAIMER } from "@/lib/orama-mocks";
import type { ValidationResult } from "@/types/orama";

const DATASET_ID = "demo-dataset-001";

export default function ValidationPage() {
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadValidation = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/orama/datasets/${DATASET_ID}/validate`, {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error("Validation request failed");
      }

      const data = (await response.json()) as ValidationResult;
      setResult(data);
    } catch {
      setError("Unable to load the mock validation result.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => {
      void loadValidation();
    });
  }, [loadValidation]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Validation"
        title="Mock contract validation"
        description={`${RESEARCH_DISCLAIMER} These results come from a scaffolded API route and are intended only to preview the research workflow.`}
      />

      <SectionCard
        title="Validation status"
        description={`Dataset ${DATASET_ID}`}
        actions={
          <button
            type="button"
            onClick={() => {
              void loadValidation();
            }}
            className="rounded-full border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-950"
          >
            Re-run mock validation
          </button>
        }
      >
        {isLoading ? <p className="text-sm text-slate-600">Loading validation output…</p> : null}
        {error ? <p className="text-sm font-medium text-rose-700">{error}</p> : null}
        {result ? (
          <div className="grid gap-4 md:grid-cols-5">
            <div className="rounded-2xl bg-slate-50 p-4"><p className="text-xs uppercase text-slate-500">Errors</p><p className="mt-2 text-2xl font-semibold">{result.summary.errorCount}</p></div>
            <div className="rounded-2xl bg-slate-50 p-4"><p className="text-xs uppercase text-slate-500">Warnings</p><p className="mt-2 text-2xl font-semibold">{result.summary.warningCount}</p></div>
            <div className="rounded-2xl bg-slate-50 p-4"><p className="text-xs uppercase text-slate-500">Participants</p><p className="mt-2 text-sm font-semibold">{result.summary.participantsSheet ? "Present" : "Missing"}</p></div>
            <div className="rounded-2xl bg-slate-50 p-4"><p className="text-xs uppercase text-slate-500">Observations</p><p className="mt-2 text-sm font-semibold">{result.summary.observationsSheet ? "Present" : "Missing"}</p></div>
            <div className="rounded-2xl bg-slate-50 p-4"><p className="text-xs uppercase text-slate-500">Data dictionary</p><p className="mt-2 text-sm font-semibold">{result.summary.dataDictionarySheet ? "Present" : "Missing"}</p></div>
          </div>
        ) : null}
      </SectionCard>

      <div className="grid gap-6 lg:grid-cols-2">
        <SectionCard title="Errors" description="Issues that block a production-style worker handoff.">
          {result?.errors.length ? (
            <ul className="space-y-4 text-sm text-slate-700">
              {result.errors.map((issue) => (
                <li key={issue.code} className="rounded-2xl border border-rose-200 bg-rose-50 p-4">
                  <p className="font-semibold text-rose-900">{issue.code} · {issue.field}</p>
                  <p className="mt-2 leading-6">{issue.message}</p>
                  {issue.suggestion ? <p className="mt-2 text-rose-800">Suggestion: {issue.suggestion}</p> : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-600">No mock errors returned.</p>
          )}
        </SectionCard>

        <SectionCard title="Warnings" description="Advisories for this synthetic research scaffold.">
          {result?.warnings.length ? (
            <ul className="space-y-4 text-sm text-slate-700">
              {result.warnings.map((issue) => (
                <li key={issue.code} className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                  <p className="font-semibold text-amber-900">{issue.code} · {issue.field}</p>
                  <p className="mt-2 leading-6">{issue.message}</p>
                  {issue.suggestion ? <p className="mt-2 text-amber-800">Suggestion: {issue.suggestion}</p> : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-600">No mock warnings returned.</p>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
