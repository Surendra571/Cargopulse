import React, { useEffect, useState } from "react";
import { dashboardApi, ShipmentDetailResponse } from "@/api/dashboard";
import { StatusBadge } from "@/components/common/StatusBadge";
import {
  X,
  Package,
  MapPin,
  AlertTriangle,
  FileCheck2,
  Clock,
} from "lucide-react";

interface ShipmentDetailModalProps {
  isOpen: boolean;
  shipmentId: string | null;
  onClose: () => void;
}

export const ShipmentDetailModal: React.FC<ShipmentDetailModalProps> = ({
  isOpen,
  shipmentId,
  onClose,
}) => {
  const [detail, setDetail] = useState<ShipmentDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !shipmentId) {
      setDetail(null);
      setError(null);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    dashboardApi
      .getShipmentDetail(shipmentId)
      .then((data) => {
        if (isMounted) setDetail(data);
      })
      .catch((err) => {
        if (isMounted) setError(err?.response?.data?.detail || "Failed to load shipment details.");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, shipmentId]);

  if (!isOpen) return null;

  const formatDate = (isoString?: string | null) => {
    if (!isoString) return "—";
    try {
      const d = new Date(isoString);
      return d.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-surface-card/60 backdrop-blur-sm animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl bg-surface-card rounded-xl shadow-2xl border border-outline-variant overflow-hidden flex flex-col max-h-[90vh] animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-outline-variant flex items-center justify-between bg-surface-container-low">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary-container border border-burnt-orange/30 flex items-center justify-center text-primary shrink-0">
              <Package className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-on-surface">
                  {detail?.tracking_number || "Shipment Details"}
                </h2>
                {detail && <StatusBadge status={detail.status} size="sm" />}
              </div>
              <p className="text-xs text-on-surface-muted">
                {detail
                  ? `${detail.origin_city}, ${detail.origin_state} → ${detail.destination_city}, ${detail.destination_state}`
                  : "Loading consignment..."}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 text-on-surface-subtle hover:text-on-surface hover:bg-surface-container rounded-md transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="overflow-y-auto p-6 space-y-6">
          {loading && (
            <div className="py-16 flex flex-col items-center justify-center gap-3 text-on-surface-subtle">
              <div className="w-8 h-8 rounded-full border-2 border-blue-600 border-t-transparent animate-spin" />
              <p className="text-xs font-medium">Fetching consignment telemetry...</p>
            </div>
          )}

          {error && (
            <div className="p-4 rounded-lg bg-critical-container border border-rose-200 text-on-critical-container text-xs">
              {error}
            </div>
          )}

          {detail && !loading && (
            <>
              {/* Origin & Destination Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Origin */}
                <div className="p-4 rounded-xl bg-surface-container-low border border-outline-variant space-y-2">
                  <div className="flex items-center justify-between text-xs text-on-surface-muted font-semibold uppercase">
                    <span className="flex items-center gap-1.5 text-primary">
                      <MapPin className="w-3.5 h-3.5" /> Origin Facility
                    </span>
                    <span>Dock Loading</span>
                  </div>
                  <h4 className="text-sm font-bold text-on-surface">{detail.origin_name}</h4>
                  <p className="text-xs text-on-surface-muted">{detail.origin_address}</p>
                  <p className="text-xs text-on-surface-muted">
                    Contact: {detail.origin_contact_name} &bull; {detail.origin_contact_phone}
                  </p>
                  <div className="pt-2 border-t border-outline-variant/60 flex items-center justify-between text-xs">
                    <span className="text-on-surface-muted">Scheduled:</span>
                    <span className="font-semibold text-on-surface">
                      {formatDate(detail.scheduled_pickup_time)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-on-surface-muted">Actual Pickup:</span>
                    <span
                      className={`font-bold ${
                        detail.actual_pickup_time ? "text-success" : "text-warning"
                      }`}
                    >
                      {formatDate(detail.actual_pickup_time) || "Pending arrival"}
                    </span>
                  </div>
                </div>

                {/* Destination */}
                <div className="p-4 rounded-xl bg-surface-container-low border border-outline-variant space-y-2">
                  <div className="flex items-center justify-between text-xs text-on-surface-muted font-semibold uppercase">
                    <span className="flex items-center gap-1.5 text-on-success-container">
                      <MapPin className="w-3.5 h-3.5" /> Destination Hub
                    </span>
                    <span>Consignee Delivery</span>
                  </div>
                  <h4 className="text-sm font-bold text-on-surface">{detail.destination_name}</h4>
                  <p className="text-xs text-on-surface-muted">{detail.destination_address}</p>
                  <p className="text-xs text-on-surface-muted">
                    Contact: {detail.destination_contact_name} &bull; {detail.destination_contact_phone}
                  </p>
                  <div className="pt-2 border-t border-outline-variant/60 flex items-center justify-between text-xs">
                    <span className="text-on-surface-muted">Expected:</span>
                    <span className="font-semibold text-on-surface">
                      {formatDate(detail.expected_delivery_time)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-on-surface-muted">Actual Delivery:</span>
                    <span
                      className={`font-bold ${
                        detail.actual_delivery_time ? "text-success" : "text-on-surface-muted"
                      }`}
                    >
                      {formatDate(detail.actual_delivery_time) || "In transit"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Cargo & Fleet Specs */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 rounded-lg border border-outline-variant bg-surface-card">
                  <span className="text-[11px] text-on-surface-muted block">Total Weight</span>
                  <span className="text-sm font-bold text-on-surface">
                    {detail.total_weight_kg.toLocaleString()} kg
                  </span>
                </div>
                <div className="p-3 rounded-lg border border-outline-variant bg-surface-card">
                  <span className="text-[11px] text-on-surface-muted block">Package Units</span>
                  <span className="text-sm font-bold text-on-surface">{detail.package_count} cartons</span>
                </div>
                <div className="p-3 rounded-lg border border-outline-variant bg-surface-card">
                  <span className="text-[11px] text-on-surface-muted block">Assigned Carrier</span>
                  <span className="text-sm font-bold text-on-surface truncate block">
                    {detail.transporter_name || "Unassigned"}
                  </span>
                </div>
                <div className="p-3 rounded-lg border border-outline-variant bg-surface-card">
                  <span className="text-[11px] text-on-surface-muted block">Driver & Vehicle</span>
                  <span className="text-sm font-bold text-on-surface truncate block">
                    {detail.driver_name ? `${detail.driver_name} (${detail.vehicle_plate})` : "Pending dispatch"}
                  </span>
                </div>
              </div>

              {/* Proof of Delivery Card (If verified) */}
              {detail.pod_verified && (
                <div className="p-4 rounded-xl bg-success-container/70 border border-teal-200 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-success-container0 text-white flex items-center justify-center shrink-0">
                      <FileCheck2 className="w-5 h-5" />
                    </div>
                    <div>
                      <span className="text-xs font-bold text-teal-900 flex items-center gap-1.5">
                        Electronic Proof of Delivery (e-POD) Verified
                      </span>
                      <p className="text-xs text-on-success-container">
                        Signed by <strong>{detail.pod_signatory_name}</strong> on {formatDate(detail.pod_verified_at)}
                      </p>
                    </div>
                  </div>
                  <span className="text-xs font-bold px-2 py-0.5 rounded bg-teal-200/80 text-teal-900 border border-teal-300">
                    Tamper Proof
                  </span>
                </div>
              )}

              {/* Exceptions Alert (If any) */}
              {detail.exceptions && detail.exceptions.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-xs font-bold text-rose-800 uppercase tracking-wider flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-critical" /> Operational Incidents ({detail.exceptions.length})
                  </h4>
                  <div className="space-y-2">
                    {detail.exceptions.map((exc) => (
                      <div
                        key={exc.id}
                        className="p-3 rounded-lg bg-critical-container/80 border border-rose-200 text-xs space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-rose-900">{exc.title}</span>
                          <span className="font-bold uppercase text-[10px] px-1.5 py-0.2 rounded bg-rose-200 text-rose-800">
                            {exc.severity}
                          </span>
                        </div>
                        <p className="text-on-critical-container">{exc.description}</p>
                        <p className="text-[10px] text-rose-500">
                          Reported at: {formatDate(exc.reported_at)} &bull; Status: {exc.status}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Event Stream History */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-on-surface uppercase tracking-wider flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-primary" /> Milestone Event Ledger
                </h4>
                <div className="space-y-2 max-h-48 overflow-y-auto divide-y divide-outline-variant pr-1">
                  {detail.events.map((ev) => (
                    <div key={ev.id} className="pt-2 pb-1 text-xs flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-on-surface">{ev.description}</p>
                        <p className="text-[11px] text-on-surface-subtle">
                          Type: {ev.event_type} &bull; Source: {ev.source} {ev.location_name && `&bull; ${ev.location_name}`}
                        </p>
                      </div>
                      <span className="text-[11px] font-mono text-on-surface-muted shrink-0">
                        {formatDate(ev.occurred_at)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-outline-variant bg-surface-container-low flex items-center justify-between">
          <span className="text-xs text-on-surface-subtle font-mono">
            {detail?.id ? `ID: ${detail.id}` : ""}
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-on-surface hover:bg-surface-container rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
