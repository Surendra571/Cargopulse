import React from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

export interface MetricCardProps {
  title: string;
  value: string | number;
  change?: string | number;
  trend?: "up" | "down" | "neutral";
  period?: string;
  icon?: React.ReactNode;
  accentColor?: "blue" | "teal" | "emerald" | "amber" | "rose" | "indigo" | "orange";
  loading?: boolean;
  className?: string;
  footnote?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  change,
  trend = "neutral",
  period = "vs previous period",
  icon,
  accentColor = "orange",
  loading = false,
  className,
  footnote,
}) => {
  const accentMap = {
    orange: "bg-primary-container text-primary border-outline-variant",
    blue: "bg-secondary-container text-secondary border-outline-variant",
    indigo: "bg-secondary-container text-secondary border-outline-variant",
    teal: "bg-success-container text-success border-outline-variant",
    emerald: "bg-success-container text-success border-outline-variant",
    amber: "bg-warning-container text-warning border-outline-variant",
    rose: "bg-critical-container text-critical border-outline-variant",
  };

  const currentAccent = accentMap[accentColor] || accentMap.orange;

  if (loading) {
    return (
      <div
        className={cn(
          "p-4 rounded-DEFAULT border border-outline-variant bg-surface-card animate-pulse space-y-2.5",
          className
        )}
      >
        <div className="flex justify-between items-center">
          <div className="h-3.5 w-24 bg-surface-container rounded-xs" />
          <div className="h-8 w-8 bg-surface-container-low rounded-sm" />
        </div>
        <div className="h-7 w-16 bg-surface-container rounded-xs" />
        <div className="h-3.5 w-28 bg-surface-container-low rounded-xs" />
      </div>
    );
  }

  return (
    <div
      className={cn(
        "relative p-4 rounded-DEFAULT border border-outline-variant bg-surface-card hover:border-outline-strong transition-colors duration-state-change flex flex-col justify-between",
        className
      )}
    >
      <div>
        <div className="flex items-center justify-between gap-3">
          <span className="font-label text-label-sm text-on-surface-muted uppercase tracking-wider">
            {title}
          </span>
          {icon && (
            <div
              className={cn(
                "h-8 w-8 rounded-sm border flex items-center justify-center shrink-0",
                currentAccent
              )}
            >
              {icon}
            </div>
          )}
        </div>

        <div className="mt-2 font-headline text-headline-md text-on-surface tabular-nums">
          {value}
        </div>
      </div>

      {(change !== undefined || footnote) && (
        <div className="mt-3 pt-2.5 border-t border-outline-variant flex items-center justify-between text-xs">
          {change !== undefined && (
            <div className="flex items-center gap-1 font-label text-label-sm">
              {trend === "up" && (
                <span className="inline-flex items-center gap-0.5 text-success">
                  <TrendingUp className="h-3.5 w-3.5" />
                  {change}
                </span>
              )}
              {trend === "down" && (
                <span className="inline-flex items-center gap-0.5 text-critical">
                  <TrendingDown className="h-3.5 w-3.5" />
                  {change}
                </span>
              )}
              {trend === "neutral" && (
                <span className="inline-flex items-center gap-0.5 text-on-surface-muted">
                  <Minus className="h-3 w-3" />
                  {change}
                </span>
              )}
              <span className="text-on-surface-subtle font-body font-normal ml-1 truncate">
                {period}
              </span>
            </div>
          )}
          {footnote && (
            <span className="font-body text-body-sm text-on-surface-subtle truncate">
              {footnote}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
