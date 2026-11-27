import React, { useState, useEffect } from "react";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/context/ToastContext";
import {
  BarChart3,
  Calendar,
  Download,
  Truck,
  Clock,
  FileCheck,
  DollarSign,
  AlertTriangle,
  Navigation,
  Info,
  RefreshCw,
  Building2,
} from "lucide-react";

interface OverviewMetrics {
  total_shipments: number;
  successful_pickups: number;
  failed_pickups: number;
  pickup_success_rate: number;
  on_time_pickup_rate: number;
  on_time_delivery_rate: number;
  transporter_acceptance_rate: number;
  average_pickup_delay_minutes: number;
  average_delivery_delay_minutes: number;
  average_recovery_time_minutes: number;
  pod_completion_rate: number;
  exception_resolution_time_minutes: number;
  cost_per_shipment: number | null;
  total_cost: number;
  cost_shipment_count: number;
  active_exceptions_count: number;
  delivered_shipments_count: number;
  metric_definitions: Record<string, string>;
}

interface TransporterMetric {
  transporter_id: string;
  transporter_name: string;
  transporter_code?: string;
  total_bookings: number;
  accepted_bookings: number;
  rejected_bookings: number;
  expired_bookings: number;
  acceptance_rate: number;
  successful_pickups: number;
  failed_pickups: number;
  pickup_success_rate: number;
  on_time_deliveries: number;
  on_time_delivery_rate: number;
}

interface RouteMetric {
  origin: string;
  destination: string;
  lane_name: string;
  total_shipments: number;
  successful_pickups: number;
  pickup_success_rate: number;
  on_time_deliveries: number;
  on_time_delivery_rate: number;
  average_transit_time_hours: number;
  average_delay_minutes: number;
}

export const AnalyticsPage: React.FC = () => {
  const { toast } = useToast();
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<"overview" | "transporters" | "routes">("overview");

  // Filter state
  const [datePreset, setDatePreset] = useState<string>("30d");
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");

  // Data state
  const [overview, setOverview] = useState<OverviewMetrics | null>(null);
  const [transporters, setTransporters] = useState<TransporterMetric[]>([]);
  const [routes, setRoutes] = useState<RouteMetric[]>([]);
  const [showDefinition, setShowDefinition] = useState<string | null>(null);

  // Compute dates based on preset
  useEffect(() => {
    const now = new Date();
    let start: Date | null = null;
    if (datePreset === "7d") {
      start = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    } else if (datePreset === "30d") {
      start = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
    } else if (datePreset === "90d") {
      start = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
    } else if (datePreset === "all") {
      start = null;
    }

    if (start) {
      setStartDate(start.toISOString().split("T")[0]);
      setEndDate(now.toISOString().split("T")[0]);
    } else if (datePreset === "all") {
      setStartDate("");
      setEndDate("");
    }
  }, [datePreset]);

  // Load analytics bundle
  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      const params: Record<string, string> = {};
      if (startDate) params.start_date = new Date(startDate).toISOString();
      if (endDate) {
        const eDate = new Date(endDate);
        eDate.setHours(23, 59, 59, 999);
        params.end_date = eDate.toISOString();
      }

      const res: any = await apiClient.get("/analytics/dashboard", { params });
      const payload = res?.overview ? res : res?.data || {};
      setOverview(payload.overview);
      setTransporters(payload.transporters || []);
      setRoutes(payload.routes || []);
    } catch (err: any) {
      toast.error(err?.message || "Failed to load analytics metrics");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, [startDate, endDate]);

  const handleExportCSV = async () => {
    try {
      const params: Record<string, string> = {};
      if (startDate) params.start_date = new Date(startDate).toISOString();
      if (endDate) params.end_date = new Date(endDate).toISOString();

      const response: any = await apiClient.get("/analytics/export", {
        params,
        responseType: "blob",
      });

      const blobData = response instanceof Blob ? response : response?.data ?? response;
      const url = window.URL.createObjectURL(new Blob([blobData]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `cargopulse_analytics_${new Date().toISOString().slice(0, 10)}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.success("Analytics report exported successfully");
    } catch {
      toast.error("Failed to export analytics report");
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header and Filter Controls */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-surface-card p-5 rounded-xl border border-outline-variant shadow-sm">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-primary-container text-primary rounded-lg">
              <BarChart3 className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-on-surface">CargoPulse Analytics</h1>
              <p className="text-sm text-on-surface-muted">
                Logistics performance, transporter reliability metrics, and lane accountability
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Preset Buttons */}
          <div className="inline-flex rounded-lg border border-outline-variant p-1 bg-surface-container-low text-xs font-medium">
            <button
              onClick={() => setDatePreset("7d")}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                datePreset === "7d" ? "bg-surface-card text-primary shadow-sm font-semibold" : "text-on-surface-muted hover:text-on-surface"
              }`}
            >
              7 Days
            </button>
            <button
              onClick={() => setDatePreset("30d")}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                datePreset === "30d" ? "bg-surface-card text-primary shadow-sm font-semibold" : "text-on-surface-muted hover:text-on-surface"
              }`}
            >
              30 Days
            </button>
            <button
              onClick={() => setDatePreset("90d")}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                datePreset === "90d" ? "bg-surface-card text-primary shadow-sm font-semibold" : "text-on-surface-muted hover:text-on-surface"
              }`}
            >
              90 Days
            </button>
            <button
              onClick={() => setDatePreset("all")}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                datePreset === "all" ? "bg-surface-card text-primary shadow-sm font-semibold" : "text-on-surface-muted hover:text-on-surface"
              }`}
            >
              All Time
            </button>
          </div>

          {/* Date Picker inputs */}
          <div className="flex items-center gap-2 bg-surface-container-low border border-outline-variant rounded-lg px-2.5 py-1.5">
            <Calendar className="w-4 h-4 text-on-surface-subtle" />
            <input
              type="date"
              value={startDate}
              onChange={(e) => {
                setDatePreset("custom");
                setStartDate(e.target.value);
              }}
              className="bg-transparent text-xs text-on-surface outline-none"
            />
            <span className="text-on-surface-subtle text-xs">-</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => {
                setDatePreset("custom");
                setEndDate(e.target.value);
              }}
              className="bg-transparent text-xs text-on-surface outline-none"
            />
          </div>

          <button
            onClick={fetchAnalytics}
            disabled={loading}
            className="p-2 border border-outline-variant hover:bg-surface-container-low rounded-lg text-on-surface-muted transition"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>

          <button
            onClick={handleExportCSV}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-primary hover:bg-burnt-orange text-white text-xs font-semibold rounded-lg shadow-sm transition"
          >
            <Download className="w-4 h-4" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-outline-variant space-x-6">
        <button
          onClick={() => setActiveTab("overview")}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition ${
            activeTab === "overview"
              ? "border-blue-600 text-primary"
              : "border-transparent text-on-surface-muted hover:text-on-surface"
          }`}
        >
          <BarChart3 className="w-4 h-4" />
          Overview KPIs
        </button>
        <button
          onClick={() => setActiveTab("transporters")}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition ${
            activeTab === "transporters"
              ? "border-blue-600 text-primary"
              : "border-transparent text-on-surface-muted hover:text-on-surface"
          }`}
        >
          <Building2 className="w-4 h-4" />
          Transporter Performance ({transporters.length})
        </button>
        <button
          onClick={() => setActiveTab("routes")}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition ${
            activeTab === "routes"
              ? "border-blue-600 text-primary"
              : "border-transparent text-on-surface-muted hover:text-on-surface"
          }`}
        >
          <Navigation className="w-4 h-4" />
          Route-Level Reliability ({routes.length})
        </button>
      </div>

      {/* TAB 1: OVERVIEW METRIC CARDS */}
      {activeTab === "overview" && overview && (
        <div className="space-y-6">
          {/* Top 4 primary rates */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Pickup Success Rate */}
            <div className="bg-surface-card p-5 rounded-xl border border-outline-variant shadow-sm relative overflow-hidden">
              <div className="flex items-center justify-between text-on-surface-muted text-xs font-medium">
                <span>Pickup Success Rate</span>
                <button
                  onClick={() => setShowDefinition(showDefinition === "pickup_success_rate" ? null : "pickup_success_rate")}
                  className="text-on-surface-subtle hover:text-on-surface-muted"
                >
                  <Info className="w-4 h-4" />
                </button>
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-extrabold text-on-surface">{overview.pickup_success_rate}%</span>
                <span className="text-xs text-on-surface-muted">
                  ({overview.successful_pickups} / {overview.successful_pickups + overview.failed_pickups})
                </span>
              </div>
              <div className="mt-2 w-full bg-surface-container rounded-full h-1.5">
                <div
                  className={`h-1.5 rounded-full ${
                    overview.pickup_success_rate >= 90
                      ? "bg-success-container0"
                      : overview.pickup_success_rate >= 75
                      ? "bg-warning-container0"
                      : "bg-critical-container0"
                  }`}
                  style={{ width: `${Math.min(overview.pickup_success_rate, 100)}%` }}
                />
              </div>
              {showDefinition === "pickup_success_rate" && (
                <div className="mt-2 p-2 bg-primary-container text-blue-900 text-xs rounded border border-burnt-orange/30">
                  {overview.metric_definitions.pickup_success_rate}
                </div>
              )}
            </div>

            {/* On-Time Pickup Rate */}
            <div className="bg-surface-card p-5 rounded-xl border border-outline-variant shadow-sm">
              <div className="flex items-center justify-between text-on-surface-muted text-xs font-medium">
                <span>On-Time Pickup Rate</span>
                <button
                  onClick={() => setShowDefinition(showDefinition === "on_time_pickup_rate" ? null : "on_time_pickup_rate")}
                  className="text-on-surface-subtle hover:text-on-surface-muted"
                >
                  <Info className="w-4 h-4" />
                </button>
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-extrabold text-on-surface">{overview.on_time_pickup_rate}%</span>
                <span className="text-xs text-on-surface-muted">&le; 15m delta</span>
              </div>
              <div className="mt-2 w-full bg-surface-container rounded-full h-1.5">
                <div
                  className="h-1.5 rounded-full bg-primary-container0"
                  style={{ width: `${Math.min(overview.on_time_pickup_rate, 100)}%` }}
                />
              </div>
              {showDefinition === "on_time_pickup_rate" && (
                <div className="mt-2 p-2 bg-primary-container text-blue-900 text-xs rounded border border-burnt-orange/30">
                  {overview.metric_definitions.on_time_pickup_rate}
                </div>
              )}
            </div>

            {/* On-Time Delivery Rate */}
            <div className="bg-surface-card p-5 rounded-xl border border-outline-variant shadow-sm">
              <div className="flex items-center justify-between text-on-surface-muted text-xs font-medium">
                <span>On-Time Delivery Rate</span>
                <button
                  onClick={() => setShowDefinition(showDefinition === "on_time_delivery_rate" ? null : "on_time_delivery_rate")}
                  className="text-on-surface-subtle hover:text-on-surface-muted"
                >
                  <Info className="w-4 h-4" />
                </button>
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-extrabold text-on-surface">{overview.on_time_delivery_rate}%</span>
                <span className="text-xs text-on-surface-muted">({overview.delivered_shipments_count} delivered)</span>
              </div>
              <div className="mt-2 w-full bg-surface-container rounded-full h-1.5">
                <div
                  className="h-1.5 rounded-full bg-indigo-500"
                  style={{ width: `${Math.min(overview.on_time_delivery_rate, 100)}%` }}
                />
              </div>
              {showDefinition === "on_time_delivery_rate" && (
                <div className="mt-2 p-2 bg-primary-container text-blue-900 text-xs rounded border border-burnt-orange/30">
                  {overview.metric_definitions.on_time_delivery_rate}
                </div>
              )}
            </div>

            {/* Transporter Acceptance Rate */}
            <div className="bg-surface-card p-5 rounded-xl border border-outline-variant shadow-sm">
              <div className="flex items-center justify-between text-on-surface-muted text-xs font-medium">
                <span>Transporter Acceptance</span>
                <button
                  onClick={() => setShowDefinition(showDefinition === "transporter_acceptance_rate" ? null : "transporter_acceptance_rate")}
                  className="text-on-surface-subtle hover:text-on-surface-muted"
                >
                  <Info className="w-4 h-4" />
                </button>
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-extrabold text-on-surface">{overview.transporter_acceptance_rate}%</span>
                <span className="text-xs text-on-surface-muted">Tenders</span>
              </div>
              <div className="mt-2 w-full bg-surface-container rounded-full h-1.5">
                <div
                  className="h-1.5 rounded-full bg-success-container0"
                  style={{ width: `${Math.min(overview.transporter_acceptance_rate, 100)}%` }}
                />
              </div>
              {showDefinition === "transporter_acceptance_rate" && (
                <div className="mt-2 p-2 bg-primary-container text-blue-900 text-xs rounded border border-burnt-orange/30">
                  {overview.metric_definitions.transporter_acceptance_rate}
                </div>
              )}
            </div>
          </div>

          {/* Operational Efficiency Grid (Remaining 9 metrics) */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Shipment Volumes & POD */}
            <div className="bg-surface-card p-5 rounded-xl border border-outline-variant shadow-sm space-y-4">
              <h3 className="text-xs font-bold text-on-surface-muted uppercase tracking-wider flex items-center gap-2">
                <Truck className="w-4 h-4 text-primary" />
                Volume & Delivery Accountability
              </h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center py-2 border-b border-outline-variant">
                  <span className="text-sm text-on-surface-muted">Total Shipments Created</span>
                  <span className="text-base font-bold text-on-surface">{overview.total_shipments}</span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-outline-variant">
                  <span className="text-sm text-on-surface-muted">POD Completion Rate</span>
                  <span className="text-base font-bold text-on-surface flex items-center gap-1.5">
                    <FileCheck className="w-4 h-4 text-success" />
                    {overview.pod_completion_rate}%
                  </span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-outline-variant">
                  <span className="text-sm text-on-surface-muted">Successful vs Failed Pickups</span>
                  <div className="flex gap-2 text-xs font-semibold">
                    <span className="px-2 py-0.5 bg-success-container text-on-success-container rounded-full">
                      +{overview.successful_pickups} OK
                    </span>
                    <span className="px-2 py-0.5 bg-critical-container text-on-critical-container rounded-full">
                      -{overview.failed_pickups} Fail
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Delay & Latency Metrics */}
            <div className="bg-surface-card p-5 rounded-xl border border-outline-variant shadow-sm space-y-4">
              <h3 className="text-xs font-bold text-on-surface-muted uppercase tracking-wider flex items-center gap-2">
                <Clock className="w-4 h-4 text-warning" />
                Delays & Variance
              </h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center py-2 border-b border-outline-variant">
                  <span className="text-sm text-on-surface-muted">Average Pickup Delay</span>
                  <span className="text-base font-bold text-on-surface">
                    {overview.average_pickup_delay_minutes} min
                  </span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-outline-variant">
                  <span className="text-sm text-on-surface-muted">Average Delivery Delay</span>
                  <span className="text-base font-bold text-on-surface">
                    {overview.average_delivery_delay_minutes} min
                  </span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-outline-variant">
                  <span className="text-sm text-on-surface-muted">Active Unresolved Incidents</span>
                  <span className="text-base font-bold text-on-surface flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                    {overview.active_exceptions_count}
                  </span>
                </div>
              </div>
            </div>

            {/* Recovery & Financial Metrics */}
            <div className="bg-surface-card p-5 rounded-xl border border-outline-variant shadow-sm space-y-4">
              <h3 className="text-xs font-bold text-on-surface-muted uppercase tracking-wider flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-success" />
                Recovery & Financials
              </h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center py-2 border-b border-outline-variant">
                  <span className="text-sm text-on-surface-muted">Average Recovery Time</span>
                  <span className="text-base font-bold text-on-surface">
                    {overview.average_recovery_time_minutes} min
                  </span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-outline-variant">
                  <span className="text-sm text-on-surface-muted">Exception Resolution Time</span>
                  <span className="text-base font-bold text-on-surface">
                    {overview.exception_resolution_time_minutes} min
                  </span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-outline-variant">
                  <span className="text-sm text-on-surface-muted">Avg Cost Per Shipment</span>
                  <span className="text-base font-bold text-success">
                    {overview.cost_per_shipment !== null ? `$${overview.cost_per_shipment.toFixed(2)}` : "N/A"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: TRANSPORTER PERFORMANCE TABLE */}
      {activeTab === "transporters" && (
        <div className="bg-surface-card rounded-xl border border-outline-variant shadow-sm overflow-hidden">
          <div className="p-4 border-b border-outline-variant flex justify-between items-center">
            <h2 className="text-base font-bold text-on-surface">Transporter Performance Rankings</h2>
            <span className="text-xs text-on-surface-muted">{transporters.length} registered carriers evaluated</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-on-surface-muted">
              <thead className="bg-surface-container-low text-on-surface-muted uppercase text-xs tracking-wider">
                <tr>
                  <th className="py-3 px-4 font-semibold">Transporter</th>
                  <th className="py-3 px-4 font-semibold">Total Tenders</th>
                  <th className="py-3 px-4 font-semibold">Accepted</th>
                  <th className="py-3 px-4 font-semibold">Rejected / Expired</th>
                  <th className="py-3 px-4 font-semibold">Acceptance Rate</th>
                  <th className="py-3 px-4 font-semibold">Pickup Success</th>
                  <th className="py-3 px-4 font-semibold">On-Time Deliveries</th>
                  <th className="py-3 px-4 font-semibold">On-Time Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant">
                {transporters.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-on-surface-subtle">
                      No transporter performance records found for this period.
                    </td>
                  </tr>
                ) : (
                  transporters.map((t) => (
                    <tr key={t.transporter_id} className="hover:bg-surface-container-low transition">
                      <td className="py-3.5 px-4 font-medium text-on-surface">
                        {t.transporter_name}
                        {t.transporter_code && (
                          <span className="ml-2 px-1.5 py-0.5 text-xs bg-surface-container text-on-surface-muted rounded">
                            {t.transporter_code}
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 font-semibold text-on-surface">{t.total_bookings}</td>
                      <td className="py-3.5 px-4 text-success font-medium">{t.accepted_bookings}</td>
                      <td className="py-3.5 px-4 text-rose-500">
                        {t.rejected_bookings} / {t.expired_bookings}
                      </td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`font-semibold ${
                            t.acceptance_rate >= 80 ? "text-success" : "text-warning"
                          }`}
                        >
                          {t.acceptance_rate}%
                        </span>
                      </td>
                      <td className="py-3.5 px-4">
                        <span className="text-on-surface font-medium">
                          {t.successful_pickups} ({t.pickup_success_rate}%)
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-on-surface">{t.on_time_deliveries}</td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`px-2 py-0.5 text-xs font-bold rounded-full ${
                            t.on_time_delivery_rate >= 90
                              ? "bg-success-container text-on-success-container"
                              : t.on_time_delivery_rate >= 75
                              ? "bg-primary-container text-primary"
                              : "bg-critical-container text-on-critical-container"
                          }`}
                        >
                          {t.on_time_delivery_rate}%
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: ROUTE-LEVEL RELIABILITY */}
      {activeTab === "routes" && (
        <div className="bg-surface-card rounded-xl border border-outline-variant shadow-sm overflow-hidden">
          <div className="p-4 border-b border-outline-variant flex justify-between items-center">
            <h2 className="text-base font-bold text-on-surface">Route & Lane Reliability</h2>
            <span className="text-xs text-on-surface-muted">{routes.length} active transportation corridors</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-on-surface-muted">
              <thead className="bg-surface-container-low text-on-surface-muted uppercase text-xs tracking-wider">
                <tr>
                  <th className="py-3 px-4 font-semibold">Corridor (Origin &rarr; Dest)</th>
                  <th className="py-3 px-4 font-semibold">Total Volume</th>
                  <th className="py-3 px-4 font-semibold">Pickup Success</th>
                  <th className="py-3 px-4 font-semibold">On-Time Deliveries</th>
                  <th className="py-3 px-4 font-semibold">On-Time Delivery Rate</th>
                  <th className="py-3 px-4 font-semibold">Avg Transit Duration</th>
                  <th className="py-3 px-4 font-semibold">Avg Delay</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant">
                {routes.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-on-surface-subtle">
                      No route volume records identified for the selected date window.
                    </td>
                  </tr>
                ) : (
                  routes.map((r) => (
                    <tr key={r.lane_name} className="hover:bg-surface-container-low transition">
                      <td className="py-3.5 px-4 font-semibold text-on-surface flex items-center gap-2">
                        <Navigation className="w-3.5 h-3.5 text-primary" />
                        {r.lane_name}
                      </td>
                      <td className="py-3.5 px-4 font-medium text-on-surface">{r.total_shipments}</td>
                      <td className="py-3.5 px-4">
                        <span className="text-success font-semibold">{r.pickup_success_rate}%</span>{" "}
                        <span className="text-xs text-on-surface-subtle">({r.successful_pickups})</span>
                      </td>
                      <td className="py-3.5 px-4 text-on-surface font-medium">{r.on_time_deliveries}</td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`px-2 py-0.5 text-xs font-bold rounded-full ${
                            r.on_time_delivery_rate >= 90
                              ? "bg-success-container text-on-success-container"
                              : "bg-warning-container text-on-warning-container"
                          }`}
                        >
                          {r.on_time_delivery_rate}%
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-on-surface">{r.average_transit_time_hours} hrs</td>
                      <td className="py-3.5 px-4 text-on-surface-muted">
                        {r.average_delay_minutes > 0 ? (
                          <span className="text-critical font-medium">+{r.average_delay_minutes} min</span>
                        ) : (
                          <span className="text-success font-medium">0 min (On-Time)</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
