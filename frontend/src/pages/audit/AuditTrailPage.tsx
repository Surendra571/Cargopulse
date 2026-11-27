import React, { useState, useEffect } from "react";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/context/ToastContext";
import {
  ShieldAlert,
  Search,
  Download,
  Calendar,
  Filter,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Eye,
  X,
  Copy,
  Check,
  Lock,
} from "lucide-react";

interface AuditLogItem {
  id: string;
  organization_id: string;
  user_id: string | null;
  actor_email: string | null;
  action: string;
  resource_type: string;
  resource_id: string;
  correlation_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  changes: Record<string, any>;
  created_at: string;
}

export const AuditTrailPage: React.FC = () => {
  const { toast } = useToast();
  const [loading, setLoading] = useState<boolean>(true);
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pageSize] = useState<number>(25);

  // Filters
  const [search, setSearch] = useState<string>("");
  const [actionFilter, setActionFilter] = useState<string>("");
  const [resourceTypeFilter, setResourceTypeFilter] = useState<string>("");
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");

  // Drawer modal for viewing before/after state diff
  const [selectedLog, setSelectedLog] = useState<AuditLogItem | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      const params: Record<string, any> = {
        page,
        page_size: pageSize,
      };
      if (search) params.search = search;
      if (actionFilter) params.action = actionFilter;
      if (resourceTypeFilter) params.resource_type = resourceTypeFilter;
      if (startDate) params.start_date = new Date(startDate).toISOString();
      if (endDate) {
        const eDate = new Date(endDate);
        eDate.setHours(23, 59, 59, 999);
        params.end_date = eDate.toISOString();
      }

      const res: any = await apiClient.get("/audit/logs", { params });
      const payload = res?.items ? res : res?.data || {};
      setLogs(payload.items || []);
      setTotal(payload.total || 0);
    } catch (err: any) {
      toast.error(err?.message || "Failed to load audit logs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [page, actionFilter, resourceTypeFilter, startDate, endDate]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchLogs();
  };

  const handleExportCSV = async () => {
    try {
      const params: Record<string, string> = {};
      if (actionFilter) params.action = actionFilter;
      if (resourceTypeFilter) params.resource_type = resourceTypeFilter;
      if (startDate) params.start_date = new Date(startDate).toISOString();
      if (endDate) params.end_date = new Date(endDate).toISOString();

      const response: any = await apiClient.get("/audit/export", {
        params,
        responseType: "blob",
      });

      const blobData = response instanceof Blob ? response : response?.data ?? response;
      const url = window.URL.createObjectURL(new Blob([blobData]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `cargopulse_audit_trail_${new Date().toISOString().slice(0, 10)}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.success("Audit trail exported successfully");
    } catch {
      toast.error("Failed to export audit trail");
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const getActionBadgeClass = (action: string) => {
    const act = action.toUpperCase();
    if (act.includes("CONFIRM") || act.includes("SUCCESS") || act.includes("COMPLETED")) {
      return "bg-success-container text-on-success-container border-emerald-200";
    }
    if (act.includes("FAIL") || act.includes("BREACH") || act.includes("REJECT") || act.includes("DELETE")) {
      return "bg-critical-container text-on-critical-container border-rose-200";
    }
    if (act.includes("OVERDUE") || act.includes("WARNING") || act.includes("RISK") || act.includes("EXPIRED")) {
      return "bg-warning-container text-on-warning-container border-amber-200";
    }
    return "bg-primary-container text-primary border-burnt-orange/30";
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-surface-card p-5 rounded-xl border border-outline-variant shadow-sm">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-indigo-50 text-indigo-600 rounded-lg">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-on-surface">Compliance & Audit Trail</h1>
              <span className="flex items-center gap-1 text-xs px-2 py-0.5 bg-surface-container text-on-surface-muted font-semibold rounded">
                <Lock className="w-3 h-3" />
                Immutable
              </span>
            </div>
            <p className="text-sm text-on-surface-muted">
              Tenant-scoped immutable ledger of administrative, security, and operational events
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchLogs}
            disabled={loading}
            className="p-2 border border-outline-variant hover:bg-surface-container-low rounded-lg text-on-surface-muted transition"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-sm transition"
          >
            <Download className="w-4 h-4" />
            Export Audit Log
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-surface-card p-4 rounded-xl border border-outline-variant shadow-sm space-y-3">
        <form onSubmit={handleSearchSubmit} className="flex flex-wrap items-center gap-3">
          {/* Search box */}
          <div className="relative flex-1 min-w-[240px]">
            <Search className="w-4 h-4 text-on-surface-subtle absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search action, actor email, correlation ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-surface-container-low border border-outline-variant rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          {/* Action Filter */}
          <div className="flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5 text-on-surface-subtle" />
            <select
              value={actionFilter}
              onChange={(e) => {
                setActionFilter(e.target.value);
                setPage(1);
              }}
              className="text-xs bg-surface-container-low border border-outline-variant rounded-lg px-2.5 py-1.5 focus:outline-none"
            >
              <option value="">All Actions</option>
              <option value="USER_REGISTER">USER_REGISTER</option>
              <option value="USER_LOGIN">USER_LOGIN</option>
              <option value="USER_LOGOUT">USER_LOGOUT</option>
              <option value="SHIPMENT_CREATED">SHIPMENT_CREATED</option>
              <option value="SHIPMENT_UPDATED">SHIPMENT_UPDATED</option>
              <option value="TRANSPORTER_SELECTED">TRANSPORTER_SELECTED</option>
              <option value="BOOKING_ACCEPTED">BOOKING_ACCEPTED</option>
              <option value="PICKUP_CONFIRMED">PICKUP_CONFIRMED</option>
              <option value="DELIVERY_CONFIRMED">DELIVERY_CONFIRMED</option>
              <option value="POD_SUBMITTED">POD_SUBMITTED</option>
              <option value="RECONCILIATION_EVALUATED">RECONCILIATION_EVALUATED</option>
              <option value="RECONCILIATION_CLOSED">RECONCILIATION_CLOSED</option>
              <option value="AI_RECOMMENDATION_GENERATED">AI_RECOMMENDATION_GENERATED</option>
              <option value="ROLE_PERMISSION_CHANGED">ROLE_PERMISSION_CHANGED</option>
            </select>
          </div>

          {/* Resource Filter */}
          <div>
            <select
              value={resourceTypeFilter}
              onChange={(e) => {
                setResourceTypeFilter(e.target.value);
                setPage(1);
              }}
              className="text-xs bg-surface-container-low border border-outline-variant rounded-lg px-2.5 py-1.5 focus:outline-none"
            >
              <option value="">All Resources</option>
              <option value="Shipment">Shipment</option>
              <option value="User">User</option>
              <option value="TransporterBooking">TransporterBooking</option>
              <option value="ProofOfDelivery">ProofOfDelivery</option>
              <option value="ReconciliationRecord">ReconciliationRecord</option>
              <option value="AIActionRecord">AIActionRecord</option>
              <option value="ExceptionRecord">ExceptionRecord</option>
            </select>
          </div>

          {/* Date Range */}
          <div className="flex items-center gap-2 bg-surface-container-low border border-outline-variant rounded-lg px-2.5 py-1">
            <Calendar className="w-3.5 h-3.5 text-on-surface-subtle" />
            <input
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                setPage(1);
              }}
              className="bg-transparent text-xs text-on-surface outline-none"
            />
            <span className="text-on-surface-subtle text-xs">-</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                setPage(1);
              }}
              className="bg-transparent text-xs text-on-surface outline-none"
            />
          </div>

          <button
            type="submit"
            className="px-3 py-1.5 bg-surface-container hover:bg-surface-card text-white text-xs font-medium rounded-lg transition"
          >
            Filter
          </button>
        </form>
      </div>

      {/* Audit Log Table */}
      <div className="bg-surface-card rounded-xl border border-outline-variant shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-on-surface-muted">
            <thead className="bg-surface-container-low text-on-surface-muted uppercase text-xs tracking-wider">
              <tr>
                <th className="py-3 px-4 font-semibold">Timestamp (UTC)</th>
                <th className="py-3 px-4 font-semibold">Action</th>
                <th className="py-3 px-4 font-semibold">Resource</th>
                <th className="py-3 px-4 font-semibold">Actor</th>
                <th className="py-3 px-4 font-semibold">Correlation ID</th>
                <th className="py-3 px-4 font-semibold text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-10 text-center text-on-surface-subtle">
                    No compliance audit logs matched your query.
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-surface-container-low transition">
                    <td className="py-3 px-4 text-xs text-on-surface-muted whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-block px-2.5 py-0.5 text-xs font-semibold rounded-md border ${getActionBadgeClass(
                          log.action
                        )}`}
                      >
                        {log.action}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs">
                      <div className="font-semibold text-on-surface">{log.resource_type}</div>
                      <div className="text-on-surface-subtle font-mono text-[11px] truncate max-w-[120px]" title={log.resource_id}>
                        {log.resource_id}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-xs">
                      <div className="font-medium text-on-surface">{log.actor_email || "System"}</div>
                      {log.ip_address && <div className="text-on-surface-subtle font-mono text-[11px]">{log.ip_address}</div>}
                    </td>
                    <td className="py-3 px-4 text-xs font-mono text-on-surface-muted">
                      {log.correlation_id ? (
                        <span className="truncate max-w-[140px] block" title={log.correlation_id}>
                          {log.correlation_id.slice(0, 16)}...
                        </span>
                      ) : (
                        <span className="text-on-surface-muted">-</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => setSelectedLog(log)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold bg-surface-container hover:bg-surface-container text-on-surface rounded-lg transition"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        Diff
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="p-4 border-t border-outline-variant flex items-center justify-between text-xs text-on-surface-muted">
          <div>
            Showing <span className="font-semibold text-on-surface">{logs.length}</span> of{" "}
            <span className="font-semibold text-on-surface">{total}</span> audited events
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1.5 border border-outline-variant rounded hover:bg-surface-container-low disabled:opacity-40"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="font-medium">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="p-1.5 border border-outline-variant rounded hover:bg-surface-container-low disabled:opacity-40"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* State Snapshot & Metadata Drawer */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 bg-surface-card/40 backdrop-blur-sm flex justify-end">
          <div className="w-full max-w-xl bg-surface-card h-full shadow-2xl p-6 overflow-y-auto space-y-6">
            <div className="flex justify-between items-center pb-4 border-b border-outline-variant">
              <div>
                <h3 className="text-lg font-bold text-on-surface">Audit Record Details</h3>
                <p className="text-xs text-on-surface-muted">Event ID: {selectedLog.id}</p>
              </div>
              <button
                onClick={() => setSelectedLog(null)}
                className="p-1.5 hover:bg-surface-container text-on-surface-subtle hover:text-on-surface rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Event Info */}
            <div className="bg-surface-container-low p-4 rounded-xl border border-outline-variant space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-on-surface-muted font-medium">Action:</span>
                <span className="font-bold text-on-surface">{selectedLog.action}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-on-surface-muted font-medium">Resource:</span>
                <span className="font-semibold text-on-surface">
                  {selectedLog.resource_type} ({selectedLog.resource_id})
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-on-surface-muted font-medium">Actor:</span>
                <span className="font-semibold text-on-surface">{selectedLog.actor_email || "System"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-on-surface-muted font-medium">Timestamp:</span>
                <span className="font-mono text-on-surface">{selectedLog.created_at}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-on-surface-muted font-medium">Correlation ID:</span>
                <div className="flex items-center gap-1 font-mono text-on-surface">
                  <span>{selectedLog.correlation_id || "N/A"}</span>
                  {selectedLog.correlation_id && (
                    <button
                      onClick={() => copyToClipboard(selectedLog.correlation_id!, "cid")}
                      className="text-on-surface-subtle hover:text-on-surface"
                    >
                      {copiedId === "cid" ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Sanitized Changes Payload */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <h4 className="text-xs font-bold text-on-surface uppercase tracking-wider">
                  State Changes & Attributes
                </h4>
                <button
                  onClick={() => copyToClipboard(JSON.stringify(selectedLog.changes, null, 2), "json")}
                  className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                >
                  {copiedId === "json" ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />}
                  Copy JSON
                </button>
              </div>
              <pre className="p-4 bg-surface-card text-on-surface rounded-xl text-xs font-mono overflow-x-auto max-h-96">
                {JSON.stringify(selectedLog.changes, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
