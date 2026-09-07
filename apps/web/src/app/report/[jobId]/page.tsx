"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { RESEARCH_DISCLAIMER } from "@/lib/orama-mocks";
import type { JobRecord, JobStatusResponse } from "@/types/orama";

export default function ReportPage() {
  const params = useParams();
  const rawJobId = params?.jobId;
  const jobId = Array.isArray(rawJobId) ? rawJobId[0] : rawJobId ?? "";
  const [job, setJob] = useState<JobRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) {
      return;
    }

    let disposed = false;

    const load = async () => {
      try {
        const response = await fetch(`/api/orama/jobs/${jobId}`, { cache: "no-store" });

        if (!response.ok) {
          throw new Error("Unable to load report");
        }

        const data = (await response.json()) as JobStatusResponse;

        if (!disposed) {
          setJob(data.job);
          setError(null);
        }
      } catch {
        if (!disposed) {
          setError("Unable to load the report view.");
        }
      }
    };

    void load();

    return () => {
      disposed = true;
    };
  }, [jobId]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Report"
        title={jobId ? `Research report ${jobId}` : "Research report"}
        description={`${RESEARCH_DISCLAIMER} Report content remains synthetic, exploratory, and unsuitable for patient-facing or clinical use.`}
      />

      {error ? <p className="text-sm font-medium text-rose-700">{error}</p> : null}

      <SectionCard title="Executive summary" description="Mock report narrative for a completed synthetic job.">
        {job?.result ? <p className="text-sm leading-7 text-slate-700">{job.result.report.executiveSummary}</p> : <p className="text-sm text-slate-600">Complete a mock job before viewing its report summary.</p>}
      </SectionCard>

      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <SectionCard title="Metrics" description="Illustrative only; not clinically validated.">
          {job?.result ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="text-slate-500">
                  <tr>
                    <th className="pb-3">Metric</th>
                    <th className="pb-3">Value</th>
                    <th className="pb-3">Note</th>
                  </tr>
                </thead>
                <tbody>
                  {job.result.report.metrics.map((metric) => (
                    <tr key={metric.name} className="border-t border-slate-100">
                      <td className="py-3 pr-4">{metric.name}</td>
                      <td className="py-3 pr-4 font-medium text-slate-950">{metric.value}</td>
                      <td className="py-3 text-slate-600">{metric.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-slate-600">Metrics will appear after the synthetic job reaches a completed state.</p>
          )}
        </SectionCard>

        <SectionCard title="Limitations and disclaimer" description="Carry these caveats into any downstream design discussion.">
          {job?.result ? (
            <div className="space-y-4 text-sm text-slate-700">
              <ul className="space-y-3">
                {job.result.report.limitations.map((limitation) => (
                  <li key={limitation} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    {limitation}
                  </li>
                ))}
              </ul>
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 font-medium text-amber-950">
                {job.result.report.disclaimer}
              </div>
              <div className="flex flex-col gap-3">
                <a
                  href={`/api/orama/results/${job.jobId}/download`}
                  className="inline-flex w-fit rounded-full bg-slate-950 px-5 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
                >
                  Download placeholder report
                </a>
                <Link href={`/jobs/${job.jobId}`} className="text-sm font-semibold text-sky-700">
                  Back to job detail
                </Link>
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-600">No completed synthetic report is available yet.</p>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
