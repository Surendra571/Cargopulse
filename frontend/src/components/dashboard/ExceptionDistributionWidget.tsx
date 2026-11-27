import React from "react";
import { ExceptionDistributionItem } from "@/api/dashboard";
import { AlertTriangle } from "lucide-react";

interface ExceptionDistributionWidgetProps {
  types: ExceptionDistributionItem[];
  severities: ExceptionDistributionItem[];
}

export const ExceptionDistributionWidget: React.FC<ExceptionDistributionWidgetProps> = ({
  types,
  severities,
}) => {
  const formatLabel = (val: string) => {
    return val
      .replace(/_/g, " ")
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase());
  };

  return (
    <div className="bg-surface-card rounded-xl border border-outline-variant p-5 shadow-xs space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-outline-variant">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-500" />
          <h3 className="text-sm font-bold text-on-surface">Exception Distribution</h3>
        </div>
        <span className="text-xs text-on-surface-muted font-medium">Incident Telemetry</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* By Exception Type */}
        <div className="space-y-3">
          <span className="text-xs font-bold text-on-surface uppercase tracking-wider block">
            By Incident Type
          </span>

          {types.length === 0 ? (
            <p className="text-xs text-on-surface-subtle py-3">No exceptions recorded.</p>
          ) : (
            <div className="space-y-2">
              {types.map((item) => (
                <div key={item.category} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-on-surface truncate max-w-[200px]">
                      {formatLabel(item.category)}
                    </span>
                    <span className="text-on-surface-muted font-mono text-[11px]">
                      {item.count} ({item.percentage}%)
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-surface-container overflow-hidden">
                    <div
                      style={{ width: `${item.percentage}%` }}
                      className="h-full bg-warning-container0 rounded-full transition-all duration-300"
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* By Severity */}
        <div className="space-y-3">
          <span className="text-xs font-bold text-on-surface uppercase tracking-wider block">
            By Severity Level
          </span>

          {severities.length === 0 ? (
            <p className="text-xs text-on-surface-subtle py-3">No exceptions recorded.</p>
          ) : (
            <div className="space-y-2">
              {severities.map((item) => (
                <div key={item.category} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-on-surface flex items-center gap-1.5">
                      <span
                        className={`w-2 h-2 rounded-full ${
                          item.category === "CRITICAL"
                            ? "bg-critical-container0"
                            : item.category === "HIGH"
                            ? "bg-orange-500"
                            : item.category === "MEDIUM"
                            ? "bg-warning-container0"
                            : "bg-primary-container0"
                        }`}
                      />
                      {item.category}
                    </span>
                    <span className="text-on-surface-muted font-mono text-[11px]">
                      {item.count} incident{item.count !== 1 ? "s" : ""}
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-surface-container overflow-hidden">
                    <div
                      style={{ width: `${item.percentage}%` }}
                      className={`h-full rounded-full transition-all duration-300 ${
                        item.category === "CRITICAL"
                          ? "bg-critical-container0"
                          : item.category === "HIGH"
                          ? "bg-orange-500"
                          : item.category === "MEDIUM"
                          ? "bg-warning-container0"
                          : "bg-primary-container0"
                      }`}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
