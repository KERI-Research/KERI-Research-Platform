"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { StatusBadge } from "@/components/StatusBadge";
import { RESEARCH_DISCLAIMER } from "@/lib/orama-mocks";
import type { JobRecord, JobsListResponse } from "@/types/orama";

export default function JobsPage() {
	const [jobs, setJobs] = useState<JobRecord[]>([]);
	const [error, setError] = useState<string | null>(null);
	const [isLoading, setIsLoading] = useState(true);

	const loadJobs = useCallback(async () => {
		setIsLoading(true);
		setError(null);

		try {
			const response = await fetch("/api/orama/jobs", {
				cache: "no-store",
			});

			if (!response.ok) {
				throw new Error("Unable to list jobs");
			}

			const data =
				(await response.json()) as JobsListResponse;
			setJobs(data.jobs);
		} catch {
			setError("Unable to load research jobs.");
		} finally {
			setIsLoading(false);
		}
	}, []);

	useEffect(() => {
		queueMicrotask(() => {
			void loadJobs();
		});
	}, [loadJobs]);

	return (
		<div className="space-y-6">
			<PageHeader
				eyebrow="Jobs"
				title="Research job queue"
				description={`${RESEARCH_DISCLAIMER} Review persisted research jobs and their worker-reported state.`}
			/>

			<SectionCard
				title="Job history"
				description="Each record is linked to a validated private dataset and a locked analysis configuration."
				actions={
					<button
						type="button"
						onClick={() => {
							void loadJobs();
						}}
						className="rounded-full border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-950"
					>
						Refresh
					</button>
				}
			>
				{isLoading ? (
					<p className="text-sm text-slate-600">
						Loading jobs…
					</p>
				) : null}
				{error ? (
					<p className="text-sm font-medium text-rose-700">
						{error}
					</p>
				) : null}
				{!isLoading && !jobs.length ? (
					<div className="rounded-2xl border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600">
						No research jobs yet. Create one
						from the{" "}
						<Link
							href="/analysis"
							className="font-semibold text-sky-700"
						>
							analysis configuration
						</Link>{" "}
						page.
					</div>
				) : null}
				<div className="space-y-3">
					{jobs.map((job) => (
						<Link
							key={job.jobId}
							href={`/jobs/${job.jobId}`}
							className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-5 transition hover:border-slate-300 md:flex-row md:items-center md:justify-between"
						>
							<div>
								<p className="font-semibold text-slate-950">
									{
										job.jobId
									}
								</p>
								<p className="mt-1 text-sm text-slate-600">
									Dataset{" "}
									{
										job.datasetId
									}{" "}
									·
									Created{" "}
									{new Date(
										job.createdAt,
									).toLocaleString()}
								</p>
							</div>
							<StatusBadge
								status={
									job.status
								}
							/>
						</Link>
					))}
				</div>
			</SectionCard>
		</div>
	);
}
