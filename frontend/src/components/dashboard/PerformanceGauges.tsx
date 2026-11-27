import React from "react";
import {
  PickupPerformanceBreakdown,
  DeliveryPerformanceBreakdown,
  TransporterReliabilityItem,
} from "@/api/dashboard";
import { Radio, Truck, CheckCircle2, AlertTriangle, Trophy } from "lucide-react";

interface PerformanceGaugesProps {
  pickupPerf: PickupPerformanceBreakdown;
  deliveryPerf: DeliveryPerformanceBreakdown;
  transporterRankings: TransporterReliabilityItem[];
  onSelectTransporter?: (transporterId: string) => void;
  selectedTransporterId?: string;
}

export const PerformanceGauges: React.FC<PerformanceGaugesProps> = ({
  pickupPerf,
  deliveryPerf,
  transporterRankings,
  onSelectTransporter,
  selectedTransporterId,
}) => {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
      {/* 1. Pickup Success Rate Card */}
      <div className="bg-surface-card rounded-DEFAULT border border-outline-variant p-5 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between pb-3 border-b border-outline-variant">
            <div className="flex items-center gap-2">
              <Radio className="w-4 h-4 text-success" />
              <h3 className="font-title text-title-md text-on-surface">Pickup Success Rate</h3>
            </div>
            <span className="font-label text-label-sm text-on-success-container bg-success-container px-2.5 py-0.5 rounded-full tabular-nums">
              {pickupPerf.success_rate}%
            </span>
          </div>

          <div className="py-4 flex items-center justify-between">
            {/* Visual Circular Gauge */}
            <div className="relative w-24 h-24 flex items-center justify-center shrink-0">
              <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                <path
                  className="text-surface-container"
                  strokeWidth="3.8"
                  stroke="currentColor"
                  fill="none"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
                <path
                  className="text-success transition-all duration-500 ease-out"
                  strokeDasharray={`${pickupPerf.success_rate}, 100`}
                  strokeWidth="3.8"
                  strokeLinecap="round"
                  stroke="currentColor"
                  fill="none"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
              </svg>
              <div className="absolute flex flex-col items-center">
                <span className="font-headline text-title-md text-on-surface tabular-nums">
                  {pickupPerf.success_rate}%
                </span>
                <span className="font-label text-[9px] uppercase text-on-surface-subtle">SLA</span>
              </div>
            </div>

            {/* Breakdown Stats */}
            <div className="space-y-2 text-xs flex-1 pl-4 tabular-nums">
              <div className="flex items-center justify-between">
                <span className="text-on-surface-muted">Total Commitments:</span>
                <span className="font-label text-on-surface">{pickupPerf.total_commitments}</span>
              </div>
              <div className="flex items-center justify-between text-on-success-container">
                <span className="flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-success" /> On-Time:
                </span>
                <span className="font-label">{pickupPerf.on_time}</span>
              </div>
              <div className="flex items-center justify-between text-warning">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-warning" /> Delayed:
                </span>
                <span className="font-label">{pickupPerf.delayed}</span>
              </div>
              <div className="flex items-center justify-between text-critical">
                <span className="flex items-center gap-1">
                  <AlertTriangle className="w-3.5 h-3.5 text-critical" /> Breached:
                </span>
                <span className="font-label">{pickupPerf.failed}</span>
              </div>
            </div>
          </div>
        </div>

        <p className="font-body text-body-sm text-on-surface-subtle pt-2 border-t border-outline-variant">
          Measures arrival within confirmed 2-hour dock window.
        </p>
      </div>

      {/* 2. Delivery Performance Card */}
      <div className="bg-surface-card rounded-xl border border-outline-variant p-5 shadow-xs flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between pb-3 border-b border-outline-variant">
            <div className="flex items-center gap-2">
              <Truck className="w-4 h-4 text-primary" />
              <h3 className="text-sm font-bold text-on-surface">Delivery Performance</h3>
            </div>
            <span className="text-xs font-bold text-primary bg-primary-container px-2 py-0.5 rounded-full border border-burnt-orange/30">
              {deliveryPerf.on_time_rate}% On-Time
            </span>
          </div>

          <div className="py-4 space-y-4">
            {/* Progress Bar Breakdown */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-on-surface-muted">Transit Adherence</span>
                <span className="font-bold text-on-surface">
                  {deliveryPerf.on_time} / {deliveryPerf.total_deliveries} loads
                </span>
              </div>
              <div className="w-full h-3 rounded-full bg-surface-container overflow-hidden flex">
                <div
                  style={{ width: `${deliveryPerf.on_time_rate}%` }}
                  className="bg-primary transition-all duration-500"
                  title={`On-time: ${deliveryPerf.on_time}`}
                />
                <div
                  style={{ width: `${100 - deliveryPerf.on_time_rate}%` }}
                  className="bg-amber-400 transition-all duration-500"
                  title={`Delayed: ${deliveryPerf.delayed}`}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 pt-2">
              <div className="p-2.5 rounded-lg bg-primary-container/60 border border-blue-100">
                <span className="text-[11px] text-on-surface-muted block">On-Time Arrivals</span>
                <span className="text-base font-extrabold text-blue-900">{deliveryPerf.on_time}</span>
              </div>
              <div className="p-2.5 rounded-lg bg-warning-container/60 border border-amber-100">
                <span className="text-[11px] text-on-surface-muted block">Delayed Deliveries</span>
                <span className="text-base font-extrabold text-amber-900">{deliveryPerf.delayed}</span>
              </div>
            </div>
          </div>
        </div>

        <p className="text-[11px] text-on-surface-subtle pt-2 border-t border-outline-variant">
          Electronic proof of delivery (e-POD) signed at consignee.
        </p>
      </div>

      {/* 3. Transporter Reliability Leaderboard */}
      <div className="bg-surface-card rounded-xl border border-outline-variant p-5 shadow-xs flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between pb-3 border-b border-outline-variant">
            <div className="flex items-center gap-2">
              <Trophy className="w-4 h-4 text-amber-500" />
              <h3 className="text-sm font-bold text-on-surface">Transporter Leaderboard</h3>
            </div>
            <span className="text-[11px] text-on-surface-muted font-medium">
              {transporterRankings.length} Active
            </span>
          </div>

          <div className="py-2 divide-y divide-outline-variant max-h-[170px] overflow-y-auto">
            {transporterRankings.length === 0 ? (
              <div className="py-6 text-center text-xs text-on-surface-subtle">
                No carriers registered yet.
              </div>
            ) : (
              transporterRankings.map((carrier, idx) => {
                const isSelected = selectedTransporterId === carrier.transporter_id;

                return (
                  <div
                    key={carrier.transporter_id}
                    onClick={() => onSelectTransporter?.(carrier.transporter_id)}
                    className={`flex items-center justify-between py-2 px-1 rounded-md cursor-pointer transition-colors ${
                      isSelected
                        ? "bg-primary-container/80 text-blue-900 font-medium"
                        : "hover:bg-surface-container-low text-on-surface"
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-[11px] font-bold text-on-surface-subtle w-4">#{idx + 1}</span>
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-on-surface truncate">
                          {carrier.transporter_name}
                        </p>
                        <p className="text-[10px] text-on-surface-subtle font-mono">
                          {carrier.transporter_code} &bull; {carrier.total_shipments} loads
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {carrier.active_exceptions > 0 && (
                        <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 border border-amber-200">
                          {carrier.active_exceptions} exc
                        </span>
                      )}
                      <span
                        className={`text-xs font-extrabold ${
                          carrier.reliability_score >= 95
                            ? "text-success"
                            : carrier.reliability_score >= 90
                            ? "text-primary"
                            : "text-warning"
                        }`}
                      >
                        {carrier.reliability_score}%
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        <p className="text-[11px] text-on-surface-subtle pt-2 border-t border-outline-variant flex items-center justify-between">
          <span>Click carrier to filter dashboard</span>
          {selectedTransporterId && (
            <button
              onClick={() => onSelectTransporter?.("")}
              className="text-primary hover:underline font-semibold"
            >
              Clear
            </button>
          )}
        </p>
      </div>
    </div>
  );
};
