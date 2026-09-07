import Link from "next/link";

const links = [
  { href: "/", label: "Overview" },
  { href: "/upload", label: "Upload" },
  { href: "/schema-mapping", label: "Schema Mapping" },
  { href: "/validation", label: "Validation" },
  { href: "/analysis", label: "Analysis" },
  { href: "/jobs", label: "Jobs" },
];

export function AppNav() {
  return (
    <nav className="flex flex-wrap gap-2">
      {links.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-950"
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
