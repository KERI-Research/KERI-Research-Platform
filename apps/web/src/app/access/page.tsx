import Link from "next/link";

export default function AccessPage() {
	return (
		<div className="grid min-h-screen place-items-center px-4 text-center">
			<div className="space-y-3 text-sm text-slate-600">
				<p>
					Research access is verified through the
					secure session prompt.
				</p>
				<Link
					href="/"
					className="font-semibold text-sky-700"
				>
					Continue to the research workspace
				</Link>
			</div>
		</div>
	);
}
