import Link from "next/link";

import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { RESEARCH_DISCLAIMER, SCAFFOLD_NOTICE } from "@/lib/orama-mocks";

const quickLinks = [
	{
		href: "/upload",
		title: "Upload a synthetic research dataset",
		description:
			"Send an approved file directly to private storage and create an auditable dataset record.",
	},
	{
		href: "/schema-mapping",
		title: "Map columns to the ORAMA contract",
		description:
			"Align source columns to participants, observations, outcomes, encounters, and data dictionary fields.",
	},
	{
		href: "/validation",
		title: "Review validation findings",
		description:
			"Run aggregate metadata and private-object validation before analysis.",
	},
	{
		href: "/analysis",
		title: "Configure a longitudinal analysis",
		description:
			"Set horizons and inclusion thresholds before locking a research job.",
	},
];

export default function Home() {
	return (
		<div className="space-y-6">
			<PageHeader
				eyebrow="Overview"
				title="Research workflow overview"
				description={`${RESEARCH_DISCLAIMER} This frontend demonstrates a research-only synthetic ORAMA workflow for longitudinal cancer-risk analysis planning on Vercel-compatible infrastructure.`}
			/>

			<div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
				<SectionCard
					title="What this scaffold covers"
					description="Each page models a different stage of the synthetic research journey without handling real clinical data."
				>
					<div className="space-y-4 text-sm leading-7 text-slate-600">
						<p>
							Use the upload flow to
							create a private dataset
							record, validate its
							research contract, lock
							an analysis
							configuration, and
							inspect worker-generated
							cohort and metric
							outputs.
						</p>
						<p>
							{SCAFFOLD_NOTICE}{" "}
							{RESEARCH_DISCLAIMER}
						</p>
					</div>
				</SectionCard>

				<SectionCard
					title="Guardrails"
					description="This application is intentionally constrained to non-clinical, synthetic research usage."
				>
					<ul className="space-y-3 text-sm text-slate-600">
						<li>
							• Never use this
							scaffold for diagnosis,
							triage, or treatment
							selection.
						</li>
						<li>
							• Never upload direct
							identifiers such as
							names, MRNs, addresses,
							or contact information.
						</li>
						<li>
							• Treat feasibility
							metrics and reports as
							research evidence only;
							they are not clinically
							validated.
						</li>
					</ul>
				</SectionCard>
			</div>

			<section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
				{quickLinks.map((link) => (
					<Link
						key={link.href}
						href={link.href}
						className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300"
					>
						<p className="text-sm font-semibold text-slate-950">
							{link.title}
						</p>
						<p className="mt-2 text-sm leading-6 text-slate-600">
							{link.description}
						</p>
					</Link>
				))}
			</section>
		</div>
	);
}
