"use client";

import { FormEvent, ReactNode, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface AccessState {
	accessRequired: boolean;
	configured: boolean;
	authenticated: boolean;
}

const initialState: AccessState | null = null;

export function ResearchAccessGate({ children }: { children: ReactNode }) {
	const router = useRouter();
	const [access, setAccess] = useState<AccessState | null>(initialState);
	const [accessToken, setAccessToken] = useState("");
	const [error, setError] = useState<string | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);

	useEffect(() => {
		let disposed = false;

		void fetch("/api/orama/access/session", {
			cache: "no-store",
			credentials: "same-origin",
		})
			.then(async (response) => {
				if (!response.ok) {
					throw new Error(
						"Access status is unavailable.",
					);
				}
				return response.json() as Promise<AccessState>;
			})
			.then((nextAccess) => {
				if (!disposed) {
					setAccess(nextAccess);
				}
			})
			.catch(() => {
				if (!disposed) {
					setError(
						"Research access status could not be verified.",
					);
				}
			});

		return () => {
			disposed = true;
		};
	}, []);

	async function handleSubmit(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		setError(null);
		setIsSubmitting(true);

		try {
			const response = await fetch(
				"/api/orama/access/session",
				{
					method: "POST",
					headers: {
						"Content-Type":
							"application/json",
					},
					credentials: "same-origin",
					body: JSON.stringify({ accessToken }),
				},
			);
			if (!response.ok) {
				throw new Error("Access token was rejected.");
			}
			setAccess({
				accessRequired: true,
				configured: true,
				authenticated: true,
			});
			setAccessToken("");
			const requestedPath = new URLSearchParams(
				window.location.search,
			).get("next");
			router.replace(
				requestedPath?.startsWith("/") &&
					!requestedPath.startsWith("//")
					? requestedPath
					: "/",
			);
		} catch {
			setError("The research access token was not accepted.");
		} finally {
			setIsSubmitting(false);
		}
	}

	if (!access) {
		return (
			<main className="grid min-h-screen place-items-center px-4 text-sm text-slate-600">
				{error ?? "Verifying research access..."}
			</main>
		);
	}

	if (!access.accessRequired || access.authenticated) {
		return <>{children}</>;
	}

	const configurationError = !access.configured;
	return (
		<main className="grid min-h-screen place-items-center bg-slate-50 px-4 py-8">
			<section className="w-full max-w-md border border-slate-200 bg-white p-6 shadow-sm">
				<p className="text-sm font-semibold uppercase tracking-[0.16em] text-rose-700">
					Restricted research environment
				</p>
				<h1 className="mt-3 text-2xl font-semibold text-slate-950">
					Research access required
				</h1>
				<p className="mt-3 text-sm leading-6 text-slate-600">
					ORAMA contains research-only workflow
					and output surfaces. Access is required
					before dataset or report information is
					shown.
				</p>
				{configurationError ? (
					<p className="mt-5 border border-rose-200 bg-rose-50 p-4 text-sm leading-6 text-rose-900">
						This deployment is not
						configured with a research
						access token.
					</p>
				) : (
					<form
						onSubmit={handleSubmit}
						className="mt-5 space-y-4"
					>
						<label className="block text-sm font-medium text-slate-800">
							Research access token
							<input
								type="password"
								autoComplete="current-password"
								value={
									accessToken
								}
								onChange={(
									event,
								) =>
									setAccessToken(
										event
											.target
											.value,
									)
								}
								className="mt-2 w-full border border-slate-300 px-3 py-2 outline-none focus:border-sky-600"
								required
							/>
						</label>
						<button
							type="submit"
							disabled={isSubmitting}
							className="w-full bg-slate-950 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
						>
							{isSubmitting
								? "Verifying access..."
								: "Enter research environment"}
						</button>
					</form>
				)}
				{error ? (
					<p className="mt-4 text-sm font-medium text-rose-700">
						{error}
					</p>
				) : null}
			</section>
		</main>
	);
}
