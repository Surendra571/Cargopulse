import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Search,
  Eye,
  Camera,
  Package,
  Loader2,
  FileCheck2,
} from "lucide-react";
import { listPODs, ProofOfDelivery } from "@/api/pod";

export const PODListPage: React.FC = () => {
  const [pods, setPods] = useState<ProofOfDelivery[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [pages, setPages] = useState(1);

  const [statusFilter, setStatusFilter] = useState<string>("");
  const [searchTerm, setSearchTerm] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchPODs = async () => {
    setLoading(true);
    try {
      const res = await listPODs({
        page,
        page_size: pageSize,
        status: statusFilter || undefined,
        search: searchTerm.trim() || undefined,
      });
      setPods(res.items);
      setTotal(res.total);
      setPages(res.pages);
    } catch (err) {
      console.error("Failed to load PODs", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPODs();
  }, [page, statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchPODs();
  };

  // Compute metrics from current dataset
  const verifiedCount = pods.filter((p) => p.verification_status === "VERIFIED").length;
  const pendingCount = pods.filter((p) => p.verification_status === "PENDING").length;
  const discrepancyCount = pods.filter((p) => p.verification_status === "DISCREPANCY_FLAGGED" || p.is_shortage || p.is_damaged).length;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-on-surface">Digital Proof of Delivery</h1>
          <p className="text-sm text-on-surface-muted mt-1">
            Review verifiable delivery evidence, recipient signatures, photographs, and discrepancy claims.
          </p>
        </div>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-surface-card p-5 rounded-xl border border-outline-variant shadow-sm flex items-center gap-4">
          <div className="p-3 bg-primary-container text-primary rounded-lg">
            <FileCheck2 className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs font-medium text-on-surface-muted">Total ePOD Records</span>
            <p className="text-2xl font-bold text-on-surface">{total}</p>
          </div>
        </div>

        <div className="bg-surface-card p-5 rounded-xl border border-outline-variant shadow-sm flex items-center gap-4">
          <div className="p-3 bg-warning-container text-warning rounded-lg">
            <Clock className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs font-medium text-on-surface-muted">Pending Review</span>
            <p className="text-2xl font-bold text-warning">{pendingCount}</p>
          </div>
        </div>

        <div className="bg-surface-card p-5 rounded-xl border border-outline-variant shadow-sm flex items-center gap-4">
          <div className="p-3 bg-success-container text-success rounded-lg">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs font-medium text-on-surface-muted">Clean Verified</span>
            <p className="text-2xl font-bold text-success">{verifiedCount}</p>
          </div>
        </div>

        <div className="bg-surface-card p-5 rounded-xl border border-outline-variant shadow-sm flex items-center gap-4">
          <div className="p-3 bg-red-50 text-red-600 rounded-lg">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs font-medium text-on-surface-muted">Discrepancies Flagged</span>
            <p className="text-2xl font-bold text-red-600">{discrepancyCount}</p>
          </div>
        </div>
      </div>

      {/* Controls & Search */}
      <div className="bg-surface-card p-4 rounded-xl border border-outline-variant shadow-sm flex flex-col md:flex-row gap-4 justify-between items-center">
        {/* Status Filter Tabs */}
        <div className="flex flex-wrap items-center gap-1.5 w-full md:w-auto">
          {[
            { label: "All Records", val: "" },
            { label: "Pending Verification", val: "PENDING" },
            { label: "Discrepancies", val: "DISCREPANCY_FLAGGED" },
            { label: "Verified", val: "VERIFIED" },
            { label: "Rejected", val: "REJECTED" },
          ].map((tab) => (
            <button
              key={tab.val}
              onClick={() => {
                setStatusFilter(tab.val);
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                statusFilter === tab.val
                  ? "bg-surface-card text-white shadow-sm"
                  : "bg-surface-container-low text-on-surface-muted hover:bg-surface-container border border-outline-variant"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <form onSubmit={handleSearchSubmit} className="relative w-full md:w-72">
          <input
            type="text"
            placeholder="Search tracking #, signee, driver..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-1.5 text-xs border border-outline-strong rounded-lg focus:outline-none focus:ring-2 focus:ring-burnt-orange"
          />
          <Search className="w-4 h-4 text-on-surface-subtle absolute left-3 top-2" />
        </form>
      </div>

      {/* Table Data */}
      <div className="bg-surface-card rounded-xl border border-outline-variant shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
            <p className="text-sm font-medium text-on-surface-muted">Loading proof of delivery records...</p>
          </div>
        ) : pods.length === 0 ? (
          <div className="py-16 text-center text-on-surface-muted">
            <ShieldCheck className="w-12 h-12 mx-auto text-on-surface-muted mb-2" />
            <p className="text-base font-semibold text-on-surface">No Proof of Delivery Records Found</p>
            <p className="text-xs text-on-surface-subtle max-w-sm mx-auto mt-1">
              Deliveries will appear here as drivers upload signed acknowledgements, cargo photographs, and delivery confirmations.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-surface-container-low border-b border-outline-variant text-on-surface-muted font-semibold uppercase tracking-wider">
                  <th className="py-3 px-4">Shipment</th>
                  <th className="py-3 px-4">Recipient Signee</th>
                  <th className="py-3 px-4">Delivered At</th>
                  <th className="py-3 px-4">Cargo Units</th>
                  <th className="py-3 px-4">Condition & Discrepancies</th>
                  <th className="py-3 px-4">Verification</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant">
                {pods.map((p) => {
                  const hasDiscrepancy = p.is_shortage || p.is_damaged;
                  return (
                    <tr key={p.id} className="hover:bg-surface-container-low transition">
                      <td className="py-3 px-4">
                        <Link
                          to={`/pod/review/${p.shipment_id}`}
                          className="font-bold text-primary hover:underline block"
                        >
                          {p.tracking_number || "Shipment"}
                        </Link>
                        <span className="text-[11px] text-on-surface-subtle">{p.delivery_location_name || "Destination facility"}</span>
                      </td>

                      <td className="py-3 px-4">
                        <span className="font-semibold text-on-surface block">{p.signed_by_name}</span>
                        {p.signed_by_designation && (
                          <span className="text-[11px] text-on-surface-subtle">{p.signed_by_designation}</span>
                        )}
                      </td>

                      <td className="py-3 px-4 text-on-surface-muted font-mono">
                        {new Date(p.signed_at).toLocaleString([], {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>

                      <td className="py-3 px-4">
                        <span className={`font-semibold ${p.is_shortage ? "text-red-600" : "text-on-surface"}`}>
                          {p.received_quantity} / {p.expected_quantity}
                        </span>
                        {p.is_shortage && (
                          <span className="text-[10px] text-red-500 block font-bold">
                            (-{p.shortage_quantity} missing)
                          </span>
                        )}
                      </td>

                      <td className="py-3 px-4">
                        <div className="flex flex-wrap items-center gap-1.5">
                          {p.is_damaged && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800">
                              <AlertTriangle className="w-3 h-3" /> Damage ({p.damage_severity})
                            </span>
                          )}
                          {p.is_shortage && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-100 text-red-800">
                              <Package className="w-3 h-3" /> Shortage
                            </span>
                          )}
                          {!hasDiscrepancy && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-success-container text-on-success-container">
                              <CheckCircle2 className="w-3 h-3" /> Clean Delivery
                            </span>
                          )}
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold font-mono ${
                          p.verification_status === "VERIFIED"
                            ? "bg-emerald-100 text-emerald-800"
                            : p.verification_status === "DISCREPANCY_FLAGGED"
                            ? "bg-amber-100 text-amber-800"
                            : p.verification_status === "REJECTED"
                            ? "bg-red-100 text-red-800"
                            : "bg-primary-container text-on-primary-container"
                        }`}>
                          {p.verification_status}
                        </span>
                      </td>

                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Link
                            to={`/pod/review/${p.shipment_id}`}
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-outline-variant text-on-surface hover:bg-surface-container font-medium text-xs transition"
                          >
                            <Eye className="w-3.5 h-3.5" /> Review
                          </Link>
                          <Link
                            to={`/pod/submit/${p.shipment_id}`}
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-surface-container text-on-surface hover:bg-surface-container font-medium text-xs transition"
                            title="Driver delivery capture"
                          >
                            <Camera className="w-3.5 h-3.5" /> Addendum
                          </Link>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {pages > 1 && (
          <div className="p-4 border-t border-outline-variant flex items-center justify-between text-xs text-on-surface-muted bg-surface-container-low">
            <span>
              Showing page <span className="font-semibold text-on-surface">{page}</span> of{" "}
              <span className="font-semibold text-on-surface">{pages}</span> ({total} total)
            </span>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1.5 rounded border border-outline-strong bg-surface-card disabled:opacity-50 hover:bg-surface-container-low"
              >
                Previous
              </button>
              <button
                disabled={page >= pages}
                onClick={() => setPage((p) => Math.min(pages, p + 1))}
                className="px-3 py-1.5 rounded border border-outline-strong bg-surface-card disabled:opacity-50 hover:bg-surface-container-low"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
