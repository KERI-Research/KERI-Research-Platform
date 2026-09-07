interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description: string;
}

export function PageHeader({ eyebrow, title, description }: PageHeaderProps) {
  return (
    <header className="space-y-3">
      {eyebrow ? <p className="text-sm font-semibold uppercase tracking-[0.2em] text-rose-700">{eyebrow}</p> : null}
      <h1 className="text-3xl font-semibold tracking-tight text-slate-950">{title}</h1>
      <p className="max-w-3xl text-sm leading-7 text-slate-600">{description}</p>
    </header>
  );
}
