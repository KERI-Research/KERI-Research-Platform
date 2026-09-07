import type { TrajectoryComparisonRow } from "@/types/orama";

interface ComparisonBarsProps {
  rows: TrajectoryComparisonRow[];
}

export function ComparisonBars({ rows }: ComparisonBarsProps) {
  return (
    <div className="space-y-4">
      {rows.map((row) => (
        <div key={row.measure} className="rounded-xl border border-slate-200 p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p className="font-medium text-slate-950">{row.measure}</p>
            <p className="text-sm text-emerald-700">Trajectory lift {row.delta.toFixed(2)}</p>
          </div>
          <div className="space-y-3">
            <div>
              <div className="mb-1 flex justify-between text-xs text-slate-600">
                <span>Static baseline</span>
                <span>{row.staticModel.toFixed(2)}</span>
              </div>
              <div className="h-3 rounded-full bg-slate-100">
                <div className="h-3 rounded-full bg-slate-500" style={{ width: `${Math.min(row.staticModel * 100, 100)}%` }} />
              </div>
            </div>
            <div>
              <div className="mb-1 flex justify-between text-xs text-slate-600">
                <span>Trajectory model</span>
                <span>{row.trajectoryModel.toFixed(2)}</span>
              </div>
              <div className="h-3 rounded-full bg-slate-100">
                <div className="h-3 rounded-full bg-emerald-500" style={{ width: `${Math.min(row.trajectoryModel * 100, 100)}%` }} />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
