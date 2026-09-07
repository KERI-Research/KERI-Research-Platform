"use client";

import { useRef, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { ACCEPTED_EXTENSIONS, RESEARCH_DISCLAIMER, SCAFFOLD_NOTICE } from "@/lib/orama-mocks";
import type { DatasetMetadataPreview } from "@/types/orama";

function formatBytes(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function extensionFor(filename: string) {
  const lastDot = filename.lastIndexOf(".");
  return lastDot >= 0 ? filename.slice(lastDot).toLowerCase() : "";
}

function parseCsvLine(line: string) {
  const cells: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];

    if (character === '"') {
      const nextCharacter = line[index + 1];

      if (inQuotes && nextCharacter === '"') {
        current += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }

      continue;
    }

    if (character === "," && !inQuotes) {
      cells.push(current.trim());
      current = "";
      continue;
    }

    current += character;
  }

  cells.push(current.trim());
  return cells;
}

async function buildPreview(file: File): Promise<DatasetMetadataPreview> {
  const extension = extensionFor(file.name);
  const preview: DatasetMetadataPreview = {
    filename: file.name,
    size: file.size,
    contentType: file.type || "Not provided by browser",
    extension,
  };

  if (extension === ".csv") {
    const text = await file.text();
    const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0);

    preview.headerRow = lines[0] ? parseCsvLine(lines[0]) : [];
    preview.rowCount = Math.max(lines.length - 1, 0);
  }

  return preview;
}

export default function UploadPage() {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<DatasetMetadataPreview | null>(null);
  const [isReading, setIsReading] = useState(false);

  async function handleFile(file: File | null) {
    setError(null);
    setPreview(null);

    if (!file) {
      return;
    }

    const extension = extensionFor(file.name);

    if (!ACCEPTED_EXTENSIONS.includes(extension as (typeof ACCEPTED_EXTENSIONS)[number])) {
      setError(`Unsupported file type. Choose one of: ${ACCEPTED_EXTENSIONS.join(", ")}.`);
      return;
    }

    setIsReading(true);

    try {
      const nextPreview = await buildPreview(file);
      setPreview(nextPreview);
    } catch {
      setError("Unable to read this file locally for preview. No content was uploaded or stored.");
    } finally {
      setIsReading(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Upload"
        title="Dataset intake scaffold"
        description={`${RESEARCH_DISCLAIMER} Preview file metadata locally only. ${SCAFFOLD_NOTICE}`}
      />

      <SectionCard title="Privacy and scope" description="This demo never transmits or persists file contents.">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
            <p className="font-semibold">Do not upload direct identifiers.</p>
            <p className="mt-2 leading-6">Exclude names, medical record numbers, addresses, phone numbers, email addresses, or other direct identifiers before using any real pipeline outside this scaffold.</p>
          </div>
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
            <p className="font-semibold">Accepted demo formats</p>
            <p className="mt-2 leading-6">Use a local .csv, .parquet, or .zip file. CSV files get a lightweight client-side header and row-count preview only.</p>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Choose a synthetic dataset file" description="Drag and drop a file or browse locally. Contents stay in your browser for this scaffold.">
        <div
          onDragEnter={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            setIsDragging(false);
          }}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            setIsDragging(false);
            void handleFile(event.dataTransfer.files.item(0));
          }}
          className={`rounded-3xl border-2 border-dashed px-6 py-12 text-center transition ${
            isDragging ? "border-sky-500 bg-sky-50" : "border-slate-300 bg-slate-50"
          }`}
        >
          <p className="text-lg font-semibold text-slate-950">Drop .csv, .parquet, or .zip here</p>
          <p className="mt-2 text-sm text-slate-600">Metadata preview only. No upload target is called in this UI scaffold.</p>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="mt-5 rounded-full bg-slate-950 px-5 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
          >
            Pick a file
          </button>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED_EXTENSIONS.join(",")}
            className="hidden"
            onChange={(event) => {
              void handleFile(event.target.files?.item(0) ?? null);
            }}
          />
        </div>
        {error ? <p className="mt-4 text-sm font-medium text-rose-700">{error}</p> : null}
        {isReading ? <p className="mt-4 text-sm text-slate-600">Reading metadata locally…</p> : null}
      </SectionCard>

      <SectionCard title="Metadata preview" description="Displayed values are derived locally in the browser and are never stored by this demo.">
        {preview ? (
          <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
            <dl className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
              <div className="flex justify-between gap-4"><dt>File name</dt><dd className="font-medium text-slate-950">{preview.filename}</dd></div>
              <div className="flex justify-between gap-4"><dt>Extension</dt><dd className="font-medium text-slate-950">{preview.extension}</dd></div>
              <div className="flex justify-between gap-4"><dt>Size</dt><dd className="font-medium text-slate-950">{formatBytes(preview.size)}</dd></div>
              <div className="flex justify-between gap-4"><dt>Browser content type</dt><dd className="font-medium text-slate-950">{preview.contentType}</dd></div>
              <div className="flex justify-between gap-4"><dt>CSV row count</dt><dd className="font-medium text-slate-950">{preview.rowCount ?? "CSV only"}</dd></div>
            </dl>
            <div className="rounded-2xl border border-slate-200 p-4">
              <p className="text-sm font-semibold text-slate-950">CSV header preview</p>
              {preview.headerRow?.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {preview.headerRow.map((column) => (
                    <span key={column} className="rounded-full bg-sky-100 px-3 py-1 text-xs font-medium text-sky-800">
                      {column}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="mt-3 text-sm text-slate-600">Header preview is available for CSV files only.</p>
              )}
              <p className="mt-4 text-sm leading-6 text-slate-600">
                {SCAFFOLD_NOTICE} The next step in a production system would call server-side routes that issue presigned private upload targets, but this page intentionally does not send any file bytes.
              </p>
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-600">No file selected yet. Choose a supported file to preview metadata locally.</p>
        )}
      </SectionCard>
    </div>
  );
}
