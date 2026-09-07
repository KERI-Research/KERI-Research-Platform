"use client";

import { useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { CONTRACT_SECTIONS, RESEARCH_DISCLAIMER, REQUIRED_CONTRACT_FIELDS, SAMPLE_COLUMNS } from "@/lib/orama-mocks";

const initialMapping = Object.fromEntries(REQUIRED_CONTRACT_FIELDS.map((field, index) => [field, SAMPLE_COLUMNS[index] ?? ""])) as Record<string, string>;

export default function SchemaMappingPage() {
  const [mapping, setMapping] = useState<Record<string, string>>(initialMapping);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Schema mapping"
        title="Map source columns to the ORAMA research contract"
        description={`${RESEARCH_DISCLAIMER} This client-side form uses mock columns only and keeps all mapping state in memory.`}
      />

      <SectionCard title="Required dataset sections" description="The downstream contract expects these logical tables or extracts.">
        <div className="flex flex-wrap gap-3">
          {CONTRACT_SECTIONS.map((section) => (
            <span key={section} className="rounded-full bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700">
              {section}
            </span>
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Field mapping workspace" description="Select a mock source column for each required contract field.">
        <div className="overflow-x-auto">
          <table className="min-w-full border-separate border-spacing-y-2 text-left text-sm">
            <thead>
              <tr className="text-slate-500">
                <th className="pb-2">Required field</th>
                <th className="pb-2">Mapped source column</th>
              </tr>
            </thead>
            <tbody>
              {REQUIRED_CONTRACT_FIELDS.map((field) => (
                <tr key={field}>
                  <td className="rounded-l-2xl border border-r-0 border-slate-200 bg-white px-4 py-3 font-medium text-slate-950">{field}</td>
                  <td className="rounded-r-2xl border border-slate-200 bg-white px-4 py-3">
                    <select
                      value={mapping[field] ?? ""}
                      onChange={(event) => {
                        setMapping((current) => ({
                          ...current,
                          [field]: event.target.value,
                        }));
                      }}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-sky-500"
                    >
                      <option value="">Unmapped</option>
                      {SAMPLE_COLUMNS.map((column) => (
                        <option key={column} value={column}>
                          {column}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>

      <SectionCard title="Current mock mapping" description="Review the current in-memory mapping summary before a real validation step.">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {REQUIRED_CONTRACT_FIELDS.map((field) => (
            <div key={field} className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm">
              <p className="font-medium text-slate-950">{field}</p>
              <p className="mt-2 text-slate-600">{mapping[field] || "Unmapped"}</p>
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  );
}
