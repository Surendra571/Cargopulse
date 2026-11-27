import React from "react";
import { cn } from "@/lib/utils";

export interface LoadingStateProps {
  type?: "spinner" | "table" | "card" | "full-page";
  text?: string;
  rows?: number;
  columns?: number;
  className?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  type = "spinner",
  text = "Loading data...",
  rows = 5,
  columns = 4,
  className,
}) => {
  if (type === "full-page") {
    return (
      <div className={cn("fixed inset-0 z-50 flex flex-col items-center justify-center bg-surface-card/40 backdrop-blur-xs", className)}>
        <div className="bg-surface-card p-6 rounded-2xl shadow-xl border border-outline-variant flex flex-col items-center gap-3">
          <div className="relative">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
            <div className="absolute inset-0 flex items-center justify-center font-bold text-[10px] text-primary">
              CP
            </div>
          </div>
          <span className="text-sm font-semibold text-on-surface">{text}</span>
        </div>
      </div>
    );
  }

  if (type === "card") {
    return (
      <div className={cn("p-6 rounded-xl border border-outline-variant bg-surface-card shadow-sm space-y-4 animate-pulse", className)}>
        <div className="h-5 w-1/3 bg-surface-container rounded" />
        <div className="h-4 w-2/3 bg-surface-container rounded" />
        <div className="space-y-2 pt-2">
          <div className="h-8 bg-surface-container rounded" />
          <div className="h-8 bg-surface-container rounded" />
        </div>
      </div>
    );
  }

  if (type === "table") {
    return (
      <div className={cn("w-full bg-surface-card rounded-xl border border-outline-variant overflow-hidden animate-pulse", className)}>
        <div className="h-10 bg-surface-container/80 border-b border-outline-variant" />
        <div className="divide-y divide-outline-variant p-2">
          {Array.from({ length: rows }).map((_, rIdx) => (
            <div key={rIdx} className="flex items-center gap-4 py-3 px-3">
              {Array.from({ length: columns }).map((_, cIdx) => (
                <div
                  key={cIdx}
                  className="h-4 bg-surface-container/80 rounded"
                  style={{ width: `${Math.max(40, 100 - cIdx * 15)}%` }}
                />
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Inline / container spinner
  return (
    <div className={cn("flex flex-col items-center justify-center py-12 px-4 gap-3", className)}>
      <div className="h-8 w-8 animate-spin rounded-full border-3 border-blue-600 border-t-transparent" />
      <span className="text-xs font-medium text-on-surface-muted">{text}</span>
    </div>
  );
};
