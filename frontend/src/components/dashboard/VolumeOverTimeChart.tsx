import React, { useState } from "react";
import { VolumeOverTimePoint } from "@/api/dashboard";
import { BarChart3 } from "lucide-react";

interface VolumeOverTimeChartProps {
  data: VolumeOverTimePoint[];
  isLoading?: boolean;
}

export const VolumeOverTimeChart: React.FC<VolumeOverTimeChartProps> = ({ data, isLoading }) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  if (isLoading) {
    return (
      <div className="bg-surface-card rounded-DEFAULT border border-outline-variant p-5 h-[300px] flex items-center justify-center">
        <div className="flex flex-col items-center gap-2 text-on-surface-muted">
          <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <span className="font-body text-body-sm">Aggregating freight volume...</span>
        </div>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="bg-surface-card rounded-DEFAULT border border-outline-variant p-5 h-[300px] flex flex-col items-center justify-center text-on-surface-muted">
        <BarChart3 className="w-8 h-8 text-on-surface-subtle mb-2" />
        <p className="font-title text-title-md text-on-surface">No volume data in selected period</p>
        <p className="font-body text-body-sm text-on-surface-subtle">Shipments created will appear here.</p>
      </div>
    );
  }

  // Calculate max height for scaling
  const maxVolume = Math.max(...data.map((d) => Math.max(d.total_shipments, d.delivered, d.exceptions)), 1);

  return (
    <div className="bg-surface-card rounded-DEFAULT border border-outline-variant p-5 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-title text-title-md text-on-surface">Shipment volume &amp; on-time pickups</h3>
            <span className="px-2 py-0.5 rounded-full bg-primary-container text-on-primary-container font-label text-label-sm">
              Daily
            </span>
          </div>
          <p className="font-body text-body-sm text-on-surface-muted">
            Total freight created, successfully delivered, and operational exceptions.
          </p>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 font-label text-label-sm text-on-surface-muted select-none">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-xs bg-burnt-orange" />
            <span>Created</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-xs bg-success" />
            <span>Delivered</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-xs bg-critical" />
            <span>Exceptions</span>
          </div>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="relative pt-6 pb-2">
        {/* Tooltip on hover */}
        {hoveredIndex !== null && data[hoveredIndex] && (
          <div className="absolute top-0 right-4 bg-secondary text-on-secondary text-xs px-3 py-1.5 rounded-sm shadow-dropdown flex items-center gap-3 z-10">
            <span className="font-mono text-mono-sm text-sidebar">{data[hoveredIndex].date}:</span>
            <span className="font-label text-label-sm tabular-nums">{data[hoveredIndex].total_shipments} Total</span>
            <span className="font-label text-label-sm text-success-container tabular-nums">{data[hoveredIndex].delivered} Delivered</span>
            {data[hoveredIndex].exceptions > 0 && (
              <span className="font-label text-label-sm text-critical-container tabular-nums">{data[hoveredIndex].exceptions} Exc</span>
            )}
          </div>
        )}

        {/* Bar columns */}
        <div className="h-44 flex items-end justify-between gap-1 sm:gap-2 px-1 border-b border-outline-variant">
          {data.map((point, idx) => {
            const totalHeight = (point.total_shipments / maxVolume) * 100;
            const delivHeight = (point.delivered / maxVolume) * 100;
            const excHeight = (point.exceptions / maxVolume) * 100;
            const isHovered = hoveredIndex === idx;

            // Short date label (MM-DD)
            const dateParts = point.date.split("-");
            const shortDate = `${dateParts[1]}/${dateParts[2]}`;

            return (
              <div
                key={point.date}
                className="flex-1 flex flex-col items-center h-full justify-end cursor-pointer group"
                onMouseEnter={() => setHoveredIndex(idx)}
                onMouseLeave={() => setHoveredIndex(null)}
              >
                {/* Stacked / Grouped Bars */}
                <div className="w-full max-w-[28px] flex items-end justify-center gap-0.5 h-full">
                  {/* Total bar */}
                  <div
                    style={{ height: `${Math.max(totalHeight, 3)}%` }}
                    className={`w-1/3 rounded-t-xs transition-all ${
                      isHovered ? "bg-blue-700 shadow-sm" : "bg-primary-container0/80 group-hover:bg-primary"
                    }`}
                  />
                  {/* Delivered bar */}
                  <div
                    style={{ height: `${Math.max(delivHeight, point.delivered > 0 ? 3 : 0)}%` }}
                    className={`w-1/3 rounded-t-xs transition-all ${
                      isHovered ? "bg-teal-600 shadow-sm" : "bg-teal-400/90 group-hover:bg-success-container0"
                    }`}
                  />
                  {/* Exceptions bar */}
                  <div
                    style={{ height: `${Math.max(excHeight, point.exceptions > 0 ? 3 : 0)}%` }}
                    className={`w-1/3 rounded-t-xs transition-all ${
                      isHovered ? "bg-rose-600 shadow-sm" : "bg-rose-400/90 group-hover:bg-critical-container0"
                    }`}
                  />
                </div>

                {/* X-axis date label */}
                <span className="text-[10px] text-on-surface-subtle mt-2 font-mono group-hover:text-on-surface transition-colors">
                  {shortDate}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
