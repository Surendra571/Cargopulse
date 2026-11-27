import React, { useState, useEffect } from "react";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/context/ToastContext";
import {
  Scale,
  Search,
  Download,
  AlertTriangle,
  Clock,
  Truck,
  FileText,
  DollarSign,
  Package,
  UserCheck,
  X,
  RefreshCw
} from "lucide-react";

interface ReconciliationSummary {
  id: string;
  shipment_id: string;
  tracking_number: string;
  transporter_name: string;
  status: "PENDING" | "MATCHED" | "DISCREPANCY" | "RESOLVED" | "APPROVED" | "CLOSED";
  base_freight_charge: number;
  final_payable_amount: number;
  total_discrepancies: number;
  resolved_discrepancies: number;
  has_mismatches: boolean;
  has_missing_data: boolean;
  invoice_number?: string;
  updated_at: string;
}

interface ReconciliationItem {
  id: string;
  category: string;
  status: "OPEN" | "INVESTIGATING" | "RESOLVED" | "CLOSED";
  expected_value: string;
  actual_value: string;
  discrepancy_delta: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  is_matched: boolean;
  is_missing_data: boolean;
  assigned_user_id?: string;
  investigation_notes?: string;
  resolution_notes?: string;
  resolved_at?: string;
}

interface ReconciliationDetail {
  reconciliation: ReconciliationSummary;
  shipment_summary: {
    id: string;
    tracking_number: string;
    status: string;
    origin: string;
    destination: string;
    scheduled_pickup: string;
    expected_delivery: string;
    actual_pickup?: string;
    actual_delivery?: string;
    package_count: number;
    weight_kg: number;
  };
  items: ReconciliationItem[];
  audit_history: Array<{ id: string; action: string; changes: any; created_at: string }>;
}

export const ReconciliationPage: React.FC = () => {
  const { toast } = useToast();
  const [reconciliations, setReconciliations] = useState<ReconciliationSummary[]>([]);
  const [selectedShipmentId, setSelectedShipmentId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ReconciliationDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [, setLoadingDetail] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [searchTerm, setSearchTerm] = useState("");
  const [onlyDiscrepancies, setOnlyDiscrepancies] = useState(false);
  const [resolvingItemId, setResolvingItemId] = useState<string | null>(null);
  const [resolutionInput, setResolutionInput] = useState("");

  useEffect(() => {
    loadReconciliations();
  }, [statusFilter, onlyDiscrepancies]);

  useEffect(() => {
    if (selectedShipmentId) {
      loadDetail(selectedShipmentId);
    }
  }, [selectedShipmentId]);

  const loadReconciliations = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.append("status", statusFilter);
      if (onlyDiscrepancies) params.append("has_discrepancy_only", "true");
      const res: any = await apiClient.get<ReconciliationSummary[]>(`/api/v1/reconciliation?${params.toString()}`);
      const list = Array.isArray(res) ? res : res?.data || [];
      setReconciliations(list);
      if (list.length > 0 && !selectedShipmentId) {
        setSelectedShipmentId(list[0].shipment_id);
      }
    } catch (err) {
      toast.error("Failed to load reconciliations");
    } finally {
      setLoading(false);
    }
  };

  const loadDetail = async (shipmentId: string) => {
    setLoadingDetail(true);
    try {
      const res: any = await apiClient.get<ReconciliationDetail>(`/api/v1/reconciliation/${shipmentId}`);
      setDetail(res?.shipment_id ? res : res?.data);
    } catch (err) {
      toast.error("Failed to load comparison detail");
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleTriggerEvaluation = async () => {
    if (!selectedShipmentId) return;
    try {
      const res: any = await apiClient.post<ReconciliationDetail>(`/api/v1/reconciliation/${selectedShipmentId}/evaluate`);
      setDetail(res?.shipment_id ? res : res?.data);
      toast.success("Planned vs. actual comparison updated!");
      loadReconciliations();
    } catch (err) {
      toast.error("Evaluation failed");
    }
  };

  const handleResolveItem = async (itemId: string) => {
    if (!resolutionInput.trim()) {
      toast.error("Please enter resolution notes");
      return;
    }
    try {
      await apiClient.patch(`/api/v1/reconciliation/items/${itemId}`, {
        resolution_notes: resolutionInput,
        status: "RESOLVED"
      });
      toast.success("Discrepancy marked resolved");
      setResolvingItemId(null);
      setResolutionInput("");
      if (selectedShipmentId) loadDetail(selectedShipmentId);
    } catch (err) {
      toast.error("Failed to update discrepancy item");
    }
  };

  const handleCloseReconciliation = async () => {
    if (!selectedShipmentId) return;
    const notes = window.prompt("Enter reconciliation closure notes:") || "Closed by Operations Reviewer";
    try {
      await apiClient.post(`/api/v1/reconciliation/${selectedShipmentId}/close`, {
        closure_notes: notes
      });
      toast.success("Reconciliation closed successfully");
      loadReconciliations();
      loadDetail(selectedShipmentId);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to close reconciliation");
    }
  };

  const handleExportCSV = () => {
    window.open(`${window.location.origin}/api/v1/reconciliation/export`, "_blank");
  };

  const filteredList = reconciliations.filter((r) =>
    r.tracking_number?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    r.transporter_name?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="flex h-[calc(100vh-4rem)] bg-surface-card text-on-surface overflow-hidden">
      {/* Sidebar: Reconciliations list */}
      <div className="w-96 border-r border-outline-variant bg-surface flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-outline-variant">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-2">
              <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400">
                <Scale className="w-5 h-5" />
              </div>
              <h2 className="font-bold text-on-surface text-base">Reconciliation Center</h2>
            </div>
            <button
              onClick={handleExportCSV}
              className="p-1.5 text-on-surface-subtle hover:text-white hover:bg-surface-container rounded-lg transition"
              title="Export CSV"
            >
              <Download className="w-4 h-4" />
            </button>
          </div>

          {/* Search & Filters */}
          <div className="space-y-2">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-on-surface-muted" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search tracking # or carrier..."
                className="w-full bg-surface-card border border-outline-strong rounded-lg pl-9 pr-3 py-1.5 text-xs text-on-surface placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div className="flex items-center space-x-2">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-surface-card border border-outline-strong rounded-lg px-2 py-1 text-xs text-on-surface-muted focus:outline-none flex-1"
              >
                <option value="">All Statuses</option>
                <option value="MATCHED">Matched</option>
                <option value="DISCREPANCY">Discrepancy</option>
                <option value="RESOLVED">Resolved</option>
                <option value="CLOSED">Closed</option>
              </select>
              <label className="flex items-center space-x-1.5 text-xs text-on-surface-subtle cursor-pointer">
                <input
                  type="checkbox"
                  checked={onlyDiscrepancies}
                  onChange={(e) => setOnlyDiscrepancies(e.target.checked)}
                  className="rounded bg-surface-container border-outline-strong text-indigo-600 focus:ring-0"
                />
                <span>Mismatches only</span>
              </label>
            </div>
          </div>
        </div>

        {/* List items */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
          {loading ? (
            <div className="text-center py-10 text-xs text-on-surface-muted">Loading reconciliations...</div>
          ) : filteredList.length === 0 ? (
            <div className="text-center py-10 text-xs text-on-surface-muted">No shipments found.</div>
          ) : (
            filteredList.map((rec) => (
              <button
                key={rec.id}
                onClick={() => setSelectedShipmentId(rec.shipment_id)}
                className={`w-full text-left p-3 rounded-xl border text-xs transition ${
                  selectedShipmentId === rec.shipment_id
                    ? "bg-surface-card border-indigo-500 shadow-md"
                    : "bg-surface-card/40 hover:bg-surface-card/80 border-outline-variant"
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-semibold text-on-surface">{rec.tracking_number}</span>
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                      rec.status === "MATCHED"
                        ? "bg-success-container0/10 text-emerald-400 border border-emerald-500/20"
                        : rec.status === "CLOSED"
                        ? "bg-surface-container-high/50 text-on-surface-muted"
                        : rec.status === "RESOLVED"
                        ? "bg-primary-container0/10 text-primary border border-burnt-orange/20"
                        : "bg-warning-container0/10 text-amber-400 border border-amber-500/20"
                    }`}
                  >
                    {rec.status}
                  </span>
                </div>
                <div className="flex items-center justify-between text-on-surface-subtle text-[11px]">
                  <span>{rec.transporter_name}</span>
                  <span>${rec.final_payable_amount.toFixed(2)}</span>
                </div>
                {rec.total_discrepancies > 0 && (
                  <div className="mt-2 flex items-center space-x-2 text-[10px] text-amber-400">
                    <AlertTriangle className="w-3 h-3" />
                    <span>{rec.total_discrepancies} variance(s) flagged</span>
                  </div>
                )}
              </button>
            ))
          )}
        </div>
      </div>

      {/* Main Panel: Comparison & 6-category reconciliation */}
      <div className="flex-1 flex flex-col bg-surface-card overflow-y-auto">
        {!detail ? (
          <div className="m-auto text-center py-20 text-on-surface-muted text-sm">
            Select a shipment on the left to review its planned vs. actual reconciliation.
          </div>
        ) : (
          <div className="p-8 max-w-5xl mx-auto w-full space-y-6">
            {/* Top Shipment Bar */}
            <div className="flex items-center justify-between bg-surface p-5 rounded-2xl border border-outline-variant">
              <div>
                <div className="flex items-center space-x-3">
                  <h1 className="text-xl font-bold text-on-surface">{detail.shipment_summary.tracking_number}</h1>
                  <span
                    className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
                      detail.reconciliation.status === "MATCHED"
                        ? "bg-success-container0/10 text-emerald-400 border border-emerald-500/20"
                        : detail.reconciliation.status === "CLOSED"
                        ? "bg-surface-container-high/50 text-on-surface-muted"
                        : "bg-warning-container0/10 text-amber-400 border border-amber-500/20"
                    }`}
                  >
                    {detail.reconciliation.status}
                  </span>
                </div>
                <p className="text-xs text-on-surface-subtle mt-1">
                  {detail.shipment_summary.origin} → {detail.shipment_summary.destination} • Carrier:{" "}
                  <span className="text-on-surface font-medium">{detail.reconciliation.transporter_name}</span>
                </p>
              </div>

              <div className="flex items-center space-x-3">
                <button
                  onClick={handleTriggerEvaluation}
                  className="px-3.5 py-2 bg-surface-container hover:bg-surface-container-high text-on-surface text-xs font-medium rounded-xl border border-outline-strong flex items-center space-x-1.5 transition"
                >
                  <RefreshCw className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Re-evaluate</span>
                </button>
                {detail.reconciliation.status !== "CLOSED" && (
                  <button
                    onClick={handleCloseReconciliation}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl transition shadow-md"
                  >
                    Close Reconciliation
                  </button>
                )}
              </div>
            </div>

            {/* 6 Category Discrepancy Breakdown */}
            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-on-surface uppercase tracking-wider">
                Planned vs. Actual Logistics Comparison (6 Categories)
              </h3>

              <div className="grid grid-cols-1 gap-4">
                {detail.items.map((it) => (
                  <div
                    key={it.id}
                    className={`p-5 rounded-2xl border transition ${
                      it.is_matched
                        ? "bg-secondary/40 border-outline-variant/80"
                        : it.is_missing_data
                        ? "bg-surface border-amber-500/30"
                        : "bg-surface border-rose-500/30"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center space-x-2.5">
                        <div
                          className={`p-2 rounded-xl ${
                            it.is_matched
                              ? "bg-success-container0/10 text-emerald-400"
                              : it.is_missing_data
                              ? "bg-warning-container0/10 text-amber-400"
                              : "bg-critical-container0/10 text-rose-400"
                          }`}
                        >
                          {it.category.includes("PICKUP") || it.category.includes("DELIVERY") ? (
                            <Clock className="w-4 h-4" />
                          ) : it.category.includes("QUANTITY") ? (
                            <Package className="w-4 h-4" />
                          ) : it.category.includes("TRANSPORTER") ? (
                            <Truck className="w-4 h-4" />
                          ) : it.category.includes("POD") ? (
                            <FileText className="w-4 h-4" />
                          ) : (
                            <DollarSign className="w-4 h-4" />
                          )}
                        </div>
                        <div>
                          <h4 className="font-semibold text-on-surface text-sm">
                            {it.category.replace(/_/g, " ")}
                          </h4>
                          <span className="text-[11px] text-on-surface-subtle font-mono">
                            {it.discrepancy_delta}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                            it.severity === "CRITICAL"
                              ? "bg-critical-container0/20 text-rose-300 border border-rose-500/30"
                              : it.severity === "HIGH"
                              ? "bg-warning-container0/20 text-amber-300"
                              : "bg-surface-container text-on-surface-subtle"
                          }`}
                        >
                          {it.severity}
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                            it.status === "RESOLVED" || it.status === "CLOSED"
                              ? "bg-success-container0/10 text-emerald-400"
                              : "bg-critical-container0/10 text-rose-400"
                          }`}
                        >
                          {it.status}
                        </span>
                      </div>
                    </div>

                    {/* Expected vs Actual Row */}
                    <div className="grid grid-cols-2 gap-4 bg-surface-card/60 p-3.5 rounded-xl text-xs mb-3">
                      <div>
                        <span className="text-on-surface-muted block text-[10px] uppercase font-bold tracking-wider">
                          Planned / Expected
                        </span>
                        <span className="text-on-surface font-mono mt-0.5 block">
                          {it.expected_value || "N/A"}
                        </span>
                      </div>
                      <div>
                        <span className="text-on-surface-muted block text-[10px] uppercase font-bold tracking-wider">
                          Actual Execution
                        </span>
                        <span
                          className={`font-mono mt-0.5 block ${
                            it.is_missing_data
                              ? "text-amber-400 italic"
                              : it.is_matched
                              ? "text-emerald-400"
                              : "text-rose-400"
                          }`}
                        >
                          {it.actual_value || (it.is_missing_data ? "Missing execution evidence" : "Mismatch")}
                        </span>
                      </div>
                    </div>

                    {/* Investigation / Resolution Section */}
                    {it.resolution_notes && (
                      <div className="p-3 bg-emerald-950/20 border border-emerald-500/20 rounded-xl text-xs text-emerald-300 mb-2">
                        <span className="font-semibold block mb-0.5">Resolution Notes:</span>
                        {it.resolution_notes}
                      </div>
                    )}

                    {!it.is_matched && it.status !== "RESOLVED" && it.status !== "CLOSED" && (
                      <div className="mt-2 flex items-center justify-end space-x-2">
                        {resolvingItemId === it.id ? (
                          <div className="flex items-center space-x-2 w-full">
                            <input
                              type="text"
                              value={resolutionInput}
                              onChange={(e) => setResolutionInput(e.target.value)}
                              placeholder="Enter investigation & resolution explanation..."
                              className="flex-1 bg-surface-card border border-outline-strong rounded-lg px-3 py-1.5 text-xs text-on-surface placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                            />
                            <button
                              onClick={() => handleResolveItem(it.id)}
                              className="px-3 py-1.5 bg-emerald-600 hover:bg-success-container0 text-white rounded-lg text-xs font-semibold"
                            >
                              Save Resolution
                            </button>
                            <button
                              onClick={() => setResolvingItemId(null)}
                              className="p-1.5 text-on-surface-subtle hover:text-white"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => {
                              setResolvingItemId(it.id);
                              setResolutionInput("");
                            }}
                            className="px-3 py-1.5 bg-surface-container hover:bg-surface-container-high text-on-surface-muted hover:text-white rounded-lg text-xs font-medium border border-outline-strong flex items-center space-x-1.5"
                          >
                            <UserCheck className="w-3.5 h-3.5 text-indigo-400" />
                            <span>Investigate & Resolve</span>
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Audit Trail */}
            {detail.audit_history.length > 0 && (
              <div className="bg-surface p-5 rounded-2xl border border-outline-variant space-y-3">
                <h4 className="text-xs font-bold text-on-surface-subtle uppercase tracking-wider">
                  Reconciliation Audit Trail
                </h4>
                <div className="space-y-2">
                  {detail.audit_history.map((a) => (
                    <div key={a.id} className="text-xs flex items-center justify-between text-on-surface-subtle py-1 border-b border-slate-900">
                      <div>
                        <span className="font-semibold text-on-surface">{a.action}</span>
                        <span className="text-on-surface-muted ml-2 font-mono">
                          {JSON.stringify(a.changes)}
                        </span>
                      </div>
                      <span className="text-[10px] text-on-surface-muted">
                        {new Date(a.created_at).toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
