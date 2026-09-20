import { ReactNode } from "react";

export default function EmptyState({
  icon,
  title,
  description,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
}) {
  return (
    <div className="card p-12 text-center animate-fade-in">
      {icon && (
        <div className="w-12 h-12 rounded-xl bg-panel-hover flex items-center justify-center mx-auto mb-4 text-gray-500">
          {icon}
        </div>
      )}
      <div className="font-semibold mb-1">{title}</div>
      {description && (
        <div className="text-sm text-gray-500 max-w-md mx-auto">
          {description}
        </div>
      )}
    </div>
  );
}