import type { JobStatus } from "@/types/orama";

const statusClasses: Record<JobStatus, string> = {
  QUEUED: "bg-slate-100 text-slate-700",
  RUNNING: "bg-sky-100 text-sky-700",
  SUCCEEDED: "bg-emerald-100 text-emerald-700",
  FAILED: "bg-rose-100 text-rose-700",
  NOT_EVALUABLE: "bg-amber-100 text-amber-700",
};

export function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold tracking-wide ${statusClasses[status]}`}>
      {status}
    </span>
  );
}
