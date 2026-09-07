"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { DEFAULT_ANALYSIS_CONFIG, RESEARCH_DISCLAIMER } from "@/lib/orama-mocks";
import type { CreateJobResponse } from "@/types/orama";

const DATASET_ID = "demo-dataset-001";

function parseHorizons(raw: string) {
  return raw
    .split(",")
    .map((value) => Number(value.trim()))
    .filter((value) => Number.isFinite(value) && value > 0);
}

export default function AnalysisPage() {
  const router = useRouter();
  const [horizonsInput, setHorizonsInput] = useState(DEFAULT_ANALYSIS_CONFIG.horizons.join(", "));
  const [minHistoryDays, setMinHistoryDays] = useState<number>(DEFAULT_ANALYSIS_CONFIG.min_history_days);
  const [minObservations, setMinObservations] = useState<number>(DEFAULT_ANALYSIS_CONFIG.min_observations_per_variable);
  const [predictionGapDays, setPredictionGapDays] = useState<number>(DEFAULT_ANALYSIS_CONFIG.prediction_gap_days);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const parsedHorizons = useMemo(() => parseHorizons(horizonsInput), [horizonsInput]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!parsedHorizons.length) {
      setError("Provide at least one positive horizon value.");
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await fetch("/api/orama/jobs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          datasetId: DATASET_ID,
          config: {
            horizons: parsedHorizons,
            min_history_days: minHistoryDays,
            min_observations_per_variable: minObservations,
            prediction_gap_days: predictionGapDays,
          },
        }),
      });

      if (!response.ok) {
        throw new Error("Job creation failed");
      }

      const data = (await response.json()) as CreateJobResponse;
      router.push(`/jobs/${data.jobId}`);
    } catch {
      setError("Unable to create the mock analysis job.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Analysis"
        title="Configure a synthetic longitudinal analysis"
        description={`${RESEARCH_DISCLAIMER} Submitting this form creates a mock server-side job record only.`}
      />

      <SectionCard title="Analysis parameters" description={`Using dataset ${DATASET_ID}. The resulting job is synthetic and non-clinical.`}>
        <form onSubmit={handleSubmit} className="grid gap-5 lg:grid-cols-2">
          <label className="space-y-2 text-sm text-slate-700">
            <span className="font-medium text-slate-950">Horizons (days)</span>
            <input
              value={horizonsInput}
              onChange={(event) => setHorizonsInput(event.target.value)}
              className="w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-sky-500"
              placeholder="30, 90, 180, 365, 730"
            />
          </label>

          <label className="space-y-2 text-sm text-slate-700">
            <span className="font-medium text-slate-950">Minimum history days</span>
            <input
              type="number"
              min={0}
              value={minHistoryDays}
              onChange={(event) => setMinHistoryDays(Number(event.target.value))}
              className="w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-sky-500"
            />
          </label>

          <label className="space-y-2 text-sm text-slate-700">
            <span className="font-medium text-slate-950">Minimum observations per variable</span>
            <input
              type="number"
              min={1}
              value={minObservations}
              onChange={(event) => setMinObservations(Number(event.target.value))}
              className="w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-sky-500"
            />
          </label>

          <label className="space-y-2 text-sm text-slate-700">
            <span className="font-medium text-slate-950">Prediction gap days</span>
            <input
              type="number"
              min={0}
              value={predictionGapDays}
              onChange={(event) => setPredictionGapDays(Number(event.target.value))}
              className="w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-sky-500"
            />
          </label>

          <div className="lg:col-span-2 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
            This form is for research-only mock job creation. It does not launch a real diagnostic model and should never be interpreted for patient care.
          </div>

          <div className="lg:col-span-2 flex flex-col gap-3 sm:flex-row sm:items-center">
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-full bg-slate-950 px-5 py-3 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {isSubmitting ? "Creating mock job…" : "Create mock job"}
            </button>
            <p className="text-sm text-slate-600">Parsed horizons: {parsedHorizons.join(", ") || "None"}</p>
          </div>

          {error ? <p className="lg:col-span-2 text-sm font-medium text-rose-700">{error}</p> : null}
        </form>
      </SectionCard>
    </div>
  );
}
