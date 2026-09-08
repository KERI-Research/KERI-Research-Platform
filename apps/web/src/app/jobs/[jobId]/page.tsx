"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ComparisonBars } from "@/components/ComparisonBars";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { StatusBadge } from "@/components/StatusBadge";
import { RESEARCH_DISCLAIMER } from "@/lib/orama-mocks";
import type { JobRecord, JobStatus, JobStatusResponse } from "@/types/orama";

const terminalStatuses: JobStatus[] = ["SUCCEEDED", "FAILED", "NOT_EVALUABLE"];

function isTerminal(status: JobStatus) {
	return terminalStatuses.includes(status);
}

export default function JobDetailPage() {
	const params = useParams();
	const router = useRouter();
	const rawJobId = params?.jobId;
	const jobId = Array.isArray(rawJobId) ? rawJobId[0] : (rawJobId ?? "");
	const [job, setJob] = useState<JobRecord | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [isSubmittingAction, setIsSubmittingAction] = useState(false);

	async function retryFailedJob() {
		if (!jobId) {
			return;
		}

		setIsSubmittingAction(true);
		setError(null);
		try {
			const response = await fetch(
				`/api/orama/jobs/${jobId}`,
				{
					method: "POST",
					headers: {
						"Content-Type":
							"application/json",
					},
					body: JSON.stringify({
						action: "retry",
					}),
				},
			);
			if (!response.ok) {
				throw new Error("Retry request failed.");
			}
			const data =
				(await response.json()) as JobStatusResponse;
			router.replace(`/jobs/${data.job.jobId}`);
		} catch {
			setError(
				"The failed job could not be retried. Confirm the worker is available and try again.",
			);
		} finally {
			setIsSubmittingAction(false);
		}
	}

	async function deleteTerminalJob() {
		if (
			!jobId ||
			!window.confirm(
				"Delete this terminal job and its private report artifacts? The dataset will be retained.",
			)
		) {
			return;
		}

		setIsSubmittingAction(true);
		setError(null);
		try {
			const response = await fetch(
				`/api/orama/jobs/${jobId}`,
				{
					method: "DELETE",
				},
			);
			if (!response.ok) {
				throw new Error("Job deletion failed.");
			}
			router.push("/jobs");
		} catch {
			setError(
				"The terminal job could not be deleted. Its private artifacts may be temporarily unavailable.",
			);
		} finally {
			setIsSubmittingAction(false);
		}
	}

	useEffect(() => {
		if (!jobId) {
			return;
		}

		let disposed = false;

		const loadJob = async () => {
			try {
				const response = await fetch(
					`/api/orama/jobs/${jobId}`,
					{ cache: "no-store" },
				);

				if (!response.ok) {
					throw new Error("Unable to load job");
				}

				const data =
					(await response.json()) as JobStatusResponse;

				if (!disposed) {
					setJob(data.job);
					setError(null);

					if (isTerminal(data.job.status)) {
						window.clearInterval(
							intervalId,
						);
					}
				}
			} catch {
				if (!disposed) {
					setError(
						"Unable to load the research job state.",
					);
				}
			}
		};

		void loadJob();
		const intervalId = window.setInterval(() => {
			void loadJob();
		}, 4000);

		return () => {
			disposed = true;
			if (intervalId) {
				window.clearInterval(intervalId);
			}
		};
	}, [jobId]);

	return (
		<div className="space-y-6">
			<PageHeader
				eyebrow="Job detail"
				title={
					jobId
						? `Research job ${jobId}`
						: "Research job"
				}
				description={`${RESEARCH_DISCLAIMER} This page polls the private worker status for the locked research job.`}
			/>

			<SectionCard
				title="Lifecycle"
				description="Polling every few seconds until the synthetic job reaches a terminal state."
			>
				{error ? (
					<p className="text-sm font-medium text-rose-700">
						{error}
					</p>
				) : null}
				{job ? (
					<div className="grid gap-4 lg:grid-cols-[1fr_1fr_auto] lg:items-center">
						<div>
							<p className="text-sm text-slate-500">
								Dataset
							</p>
							<p className="mt-1 font-semibold text-slate-950">
								{job.datasetId}
							</p>
						</div>
						<div>
							<p className="text-sm text-slate-500">
								Last updated
							</p>
							<p className="mt-1 font-semibold text-slate-950">
								{new Date(
									job.updatedAt,
								).toLocaleString()}
							</p>
						</div>
						<div className="justify-self-start lg:justify-self-end">
							<StatusBadge
								status={
									job.status
								}
							/>
						</div>
						{isTerminal(job.status) ? (
							<div className="flex flex-wrap gap-2 lg:col-span-3">
								{job.status ===
								"FAILED" ? (
									<button
										type="button"
										onClick={() => {
											void retryFailedJob();
										}}
										disabled={
											isSubmittingAction
										}
										className="rounded-full bg-sky-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-sky-800 disabled:cursor-not-allowed disabled:bg-slate-300"
									>
										{isSubmittingAction
											? "Starting retry..."
											: "Retry job"}
									</button>
								) : null}
								<button
									type="button"
									onClick={() => {
										void deleteTerminalJob();
									}}
									disabled={
										isSubmittingAction
									}
									className="rounded-full border border-rose-300 px-4 py-2 text-sm font-semibold text-rose-700 transition hover:border-rose-400 hover:text-rose-900 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
								>
									{isSubmittingAction
										? "Working..."
										: "Delete job"}
								</button>
							</div>
						) : null}
					</div>
				) : (
					<p className="text-sm text-slate-600">
						Loading job state…
					</p>
				)}
			</SectionCard>

			{job ? (
				<div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
					<div className="space-y-6">
						<SectionCard
							title="Configuration"
							description="Locked parameters submitted to the private worker."
						>
							<dl className="grid gap-3 sm:grid-cols-2 text-sm text-slate-700">
								<div className="rounded-2xl bg-slate-50 p-4">
									<dt className="text-slate-500">
										Horizons
									</dt>
									<dd className="mt-1 font-medium text-slate-950">
										{job.config.horizons.join(
											", ",
										)}{" "}
										days
									</dd>
								</div>
								<div className="rounded-2xl bg-slate-50 p-4">
									<dt className="text-slate-500">
										Min
										history
									</dt>
									<dd className="mt-1 font-medium text-slate-950">
										{
											job
												.config
												.min_history_days
										}{" "}
										days
									</dd>
								</div>
								<div className="rounded-2xl bg-slate-50 p-4">
									<dt className="text-slate-500">
										Min
										observations
									</dt>
									<dd className="mt-1 font-medium text-slate-950">
										{
											job
												.config
												.min_observations_per_variable
										}
									</dd>
								</div>
								<div className="rounded-2xl bg-slate-50 p-4">
									<dt className="text-slate-500">
										Prediction
										gap
									</dt>
									<dd className="mt-1 font-medium text-slate-950">
										{
											job
												.config
												.prediction_gap_days
										}{" "}
										days
									</dd>
								</div>
								<div className="rounded-2xl bg-slate-50 p-4">
									<dt className="text-slate-500">
										Configuration
										hash
									</dt>
									<dd className="mt-1 break-all font-mono text-xs font-medium text-slate-950">
										{job.configHash ??
											"Pending"}
									</dd>
								</div>
								<div className="rounded-2xl bg-slate-50 p-4">
									<dt className="text-slate-500">
										Analysis
										lock
									</dt>
									<dd className="mt-1 font-medium text-slate-950">
										{job.analysisLockedAt
											? new Date(
													job.analysisLockedAt,
												).toLocaleString()
											: "Pending"}
									</dd>
								</div>
							</dl>
						</SectionCard>

						<SectionCard
							title="Feasibility decision"
							description="A research conclusion only; it is never a clinical recommendation."
						>
							{job.result ? (
								<div className="space-y-3 text-sm text-slate-700">
									<p className="font-semibold text-slate-950">
										{job
											.result
											.feasibilityDecision ??
											"NOT_EVALUABLE"}
									</p>
									{job
										.result
										.decisionReasons
										?.length ? (
										<ul className="space-y-2">
											{job.result.decisionReasons.map(
												(
													reason,
												) => (
													<li
														key={
															reason
														}
														className="border-l-2 border-amber-400 pl-3"
													>
														{
															reason
														}
													</li>
												),
											)}
										</ul>
									) : null}
								</div>
							) : (
								<p className="text-sm text-slate-600">
									The
									worker
									will
									publish
									a
									feasibility
									decision
									when the
									job
									reaches
									a
									terminal
									state.
								</p>
							)}
						</SectionCard>

						<SectionCard
							title="Cohort exclusions"
							description="Exclusions derived from the worker's feasibility evaluation."
						>
							{job.result ? (
								<div className="overflow-x-auto">
									<table className="min-w-full text-left text-sm">
										<thead className="text-slate-500">
											<tr>
												<th className="pb-3">
													Reason
												</th>
												<th className="pb-3">
													Count
												</th>
												<th className="pb-3">
													Percent
												</th>
											</tr>
										</thead>
										<tbody>
											{job.result.cohortExclusions.map(
												(
													row,
												) => (
													<tr
														key={
															row.reason
														}
														className="border-t border-slate-100"
													>
														<td className="py-3 pr-4">
															{
																row.reason
															}
														</td>
														<td className="py-3 pr-4">
															{
																row.count
															}
														</td>
														<td className="py-3">
															{row.percent.toFixed(
																1,
															)}

															%
														</td>
													</tr>
												),
											)}
										</tbody>
									</table>
								</div>
							) : (
								<p className="text-sm text-slate-600">
									Available
									after
									the
									research
									job
									completes.
								</p>
							)}
						</SectionCard>

						<SectionCard
							title="Static vs trajectory comparison"
							description="Held-out comparison metrics for static and combined trajectory feature sets."
						>
							{job.result ? (
								<div className="space-y-6">
									<ComparisonBars
										rows={
											job
												.result
												.comparison
										}
									/>
									<div className="overflow-x-auto">
										<table className="min-w-full text-left text-sm">
											<thead className="text-slate-500">
												<tr>
													<th className="pb-3">
														Measure
													</th>
													<th className="pb-3">
														Static
													</th>
													<th className="pb-3">
														Trajectory
													</th>
													<th className="pb-3">
														Delta
													</th>
												</tr>
											</thead>
											<tbody>
												{job.result.comparison.map(
													(
														row,
													) => (
														<tr
															key={
																row.measure
															}
															className="border-t border-slate-100"
														>
															<td className="py-3 pr-4">
																{
																	row.measure
																}
															</td>
															<td className="py-3 pr-4">
																{row.staticModel.toFixed(
																	2,
																)}
															</td>
															<td className="py-3 pr-4">
																{row.trajectoryModel.toFixed(
																	2,
																)}
															</td>
															<td className="py-3 text-emerald-700">
																+
																{row.delta.toFixed(
																	2,
																)}
															</td>
														</tr>
													),
												)}
											</tbody>
										</table>
									</div>
								</div>
							) : (
								<p className="text-sm text-slate-600">
									Metric
									comparison
									will
									appear
									once the
									research
									job
									succeeds.
								</p>
							)}
						</SectionCard>
					</div>

					<div className="space-y-6">
						<SectionCard
							title="Warnings"
							description="Key reminders for interpreting this scaffold output."
						>
							{job.result?.warnings
								.length ? (
								<ul className="space-y-3 text-sm text-slate-700">
									{job.result.warnings.map(
										(
											warning,
										) => (
											<li
												key={
													warning
												}
												className="rounded-2xl border border-amber-200 bg-amber-50 p-4"
											>
												{
													warning
												}
											</li>
										),
									)}
								</ul>
							) : (
								<p className="text-sm text-slate-600">
									Limitations
									and
									warnings
									will
									appear
									when the
									job
									completes.
								</p>
							)}
						</SectionCard>

						<SectionCard
							title="Report actions"
							description="Exports remain synthetic and research-only."
						>
							{job.result ? (
								<div className="flex flex-col gap-3">
									<a
										href={`/api/orama/results/${job.jobId}/download`}
										className="inline-flex w-fit rounded-full bg-slate-950 px-5 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
									>
										Download
										report
									</a>
									<Link
										href={`/report/${job.jobId}`}
										className="text-sm font-semibold text-sky-700"
									>
										Open
										report
										view
									</Link>
								</div>
							) : (
								<p className="text-sm text-slate-600">
									Download
									becomes
									available
									after a
									stored
									report
									artifact
									is
									produced.
								</p>
							)}
						</SectionCard>
					</div>
				</div>
			) : null}
		</div>
	);
}
