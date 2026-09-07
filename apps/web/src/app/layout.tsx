import type { Metadata } from "next";

import { AppNav } from "@/components/AppNav";
import { ResearchBanner } from "@/components/ResearchBanner";
import { APP_NAME, RESEARCH_DISCLAIMER } from "@/lib/orama-mocks";

import "./globals.css";

export const metadata: Metadata = {
  title: APP_NAME,
  description: `${APP_NAME} is a research-only synthetic dashboard scaffold and is not for clinical decision-making.`,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full bg-slate-50 text-slate-950">
        <ResearchBanner />
        <div className="mx-auto flex min-h-[calc(100vh-53px)] w-full max-w-7xl flex-col px-4 py-6 md:px-6 lg:px-8">
          <header className="mb-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
              <div className="space-y-2">
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-rose-700">Synthetic longitudinal cancer-risk research dashboard</p>
                <h1 className="text-2xl font-semibold tracking-tight">{APP_NAME}</h1>
                <p className="max-w-3xl text-sm leading-7 text-slate-600">{RESEARCH_DISCLAIMER} This scaffold is designed for research workflow planning only and never for diagnosis, patient communication, or clinical decision support.</p>
              </div>
              <AppNav />
            </div>
          </header>
          <main className="flex-1">{children}</main>
          <footer className="mt-8 border-t border-slate-200 py-6 text-sm text-slate-500">
            Synthetic research scaffold only. No real files are stored, transmitted, or interpreted for care decisions in this demo.
          </footer>
        </div>
      </body>
    </html>
  );
}
