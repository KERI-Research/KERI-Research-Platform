import { RESEARCH_DISCLAIMER } from "@/lib/orama-mocks";

export function ResearchBanner() {
  return (
    <div className="border-b border-amber-300 bg-amber-100/90 px-4 py-3 text-center text-sm font-bold tracking-wide text-amber-950">
      {RESEARCH_DISCLAIMER}
    </div>
  );
}
