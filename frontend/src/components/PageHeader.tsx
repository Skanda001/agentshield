import { ReactNode } from "react";

export default function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between mb-8 gap-4 flex-wrap pb-4 border-b border-slate-800/80">
      <div className="max-w-3xl">
        <h2 className="text-2xl font-extrabold tracking-tight text-white font-sans">
          {title}
        </h2>
        {description && (
          <p className="text-xs text-slate-400 mt-1.5 leading-relaxed font-sans">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2.5">{actions}</div>}
    </div>
  );
}