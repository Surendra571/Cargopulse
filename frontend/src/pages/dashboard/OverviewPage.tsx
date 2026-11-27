import React, { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import { PageHeader } from "@/components/common/PageHeader";
import { MetricCard } from "@/components/common/MetricCard";
import { SearchBar } from "@/components/common/SearchBar";
import { DataTable, ColumnDef } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Pagination } from "@/components/common/Pagination";
import { VolumeOverTimeChart } from "@/components/dashboard/VolumeOverTimeChart";
import { PerformanceGauges } from "@/components/dashboard/PerformanceGauges";
import { ExceptionDistributionWidget } from "@/components/dashboard/ExceptionDistributionWidget";
import { ShipmentDetailModal } from "@/components/dashboard/ShipmentDetailModal";
import { Button } from "@/components/ui/button";
import {
  dashboardApi,
  DashboardOverviewResponse,
  DashboardShipmentItem,
  DashboardExceptionItem,
  PaginatedShipmentsResponse,
  PaginatedExceptionsResponse,
} from "@/api/dashboard";
import {
  Package,
  Radio,
  Truck,
  AlertTriangle,
  CalendarDays,
  Clock,
  CheckCircle2,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

type ActiveTab = "attention" | "upcoming" | "failed" | "exceptions" | "deliveries";

export const OverviewPage: React.FC = () => {
  const { user } = useAuth();
  const { addToast } = useToast();
  const navigate = useNavigate();

  // Filters state
  const [datePreset, setDatePreset] = useState<string>("30d");
  const [selectedTransporterId, setSelectedTransporterId] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [activeTab, setActiveTab] = useState<ActiveTab>("attention");
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);

  // Data state
  const [overview, setOverview] = useState<DashboardOverviewResponse | null>(null);
  const [overviewLoading, setOverviewLoading] = useState<boolean>(true);
  const [tableLoading, setTableLoading] = useState<boolean>(false);
  const [shipmentsData, setShipmentsData] = useState<PaginatedShipmentsResponse | null>(null);
  const [exceptionsData, setExceptionsData] = useState<PaginatedExceptionsResponse | null>(null);

  // Modal detail state
  const [selectedShipmentId, setSelectedShipmentId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  // Compute ISO date range from preset
  const dateRange = useMemo(() => {
    const now = new Date();
    let startDate: Date | undefined;
    if (datePreset === "7d") {
      startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    } else if (datePreset === "30d") {
      startDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
    } else if (datePreset === "90d") {
      startDate = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
    }
    return {
      start_date: startDate ? startDate.toISOString() : undefined,
      end_date: now.toISOString(),
    };
  }, [datePreset]);

  // Fetch Dashboard Overview (Metrics, Charts, Activity)
  const fetchOverview = async (isManualRefresh = false) => {
    setOverviewLoading(true);
    try {
      const data = await dashboardApi.getOverview({
        start_date: dateRange.start_date,
        end_date: dateRange.end_date,
        transporter_id: selectedTransporterId || undefined,
      });
      setOverview(data);
      if (isManualRefresh) {
        addToast({
          title: "Dashboard Refreshed",
          description: "Latest operational metrics loaded from primary database.",
          type: "info",
        });
      }
    } catch (err: any) {
      addToast({
        title: "Failed to load dashboard metrics",
        description: err?.response?.data?.detail || "Network error querying database.",
        type: "error",
      });
    } finally {
      setOverviewLoading(false);
    }
  };

  // Fetch Active Tab Table Data
  const fetchTableData = async () => {
    setTableLoading(true);
    const params = {
      page: currentPage,
      page_size: pageSize,
      search: searchQuery.trim() || undefined,
      transporter_id: selectedTransporterId || undefined,
    };

    try {
      if (activeTab === "attention") {
        const res = await dashboardApi.getTableAttention(params);
        setShipmentsData(res);
      } else if (activeTab === "upcoming") {
        const res = await dashboardApi.getTableUpcomingPickups(params);
        setShipmentsData(res);
      } else if (activeTab === "failed") {
        const res = await dashboardApi.getTableFailedPickups(params);
        setShipmentsData(res);
      } else if (activeTab === "deliveries") {
        const res = await dashboardApi.getTableDeliveries(params);
        setShipmentsData(res);
      } else if (activeTab === "exceptions") {
        const res = await dashboardApi.getTableExceptions(params);
        setExceptionsData(res);
      }
    } catch (err: any) {
      addToast({
        title: "Failed to load table records",
        description: err?.response?.data?.detail || "Error querying database.",
        type: "error",
      });
    } finally {
      setTableLoading(false);
    }
  };

  // Re-fetch overview when date or transporter filter changes
  useEffect(() => {
    fetchOverview();
  }, [dateRange, selectedTransporterId]);

  // Re-fetch table when active tab, pagination, search, or transporter changes
  useEffect(() => {
    fetchTableData();
  }, [activeTab, currentPage, pageSize, searchQuery, selectedTransporterId]);

  // Reset page when tab or search changes
  useEffect(() => {
    setCurrentPage(1);
  }, [activeTab, searchQuery]);

  const handleOpenDetail = (shipmentId: string) => {
    setSelectedShipmentId(shipmentId);
    setIsModalOpen(true);
  };

  const formatDate = (isoString?: string | null) => {
    if (!isoString) return "—";
    try {
      const d = new Date(isoString);
      return d.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoString;
    }
  };

  // Shipment columns for Data Table
  const shipmentColumns: ColumnDef<DashboardShipmentItem>[] = [
    {
      id: "tracking_number",
      header: "Shipment Ref",
      cell: (row) => (
        <button
          onClick={() => handleOpenDetail(row.id)}
          className="font-mono text-mono-sm font-semibold text-primary hover:text-burnt-orange hover:underline flex items-center gap-1.5 text-left cursor-pointer"
        >
          {row.tracking_number}
          {row.is_at_risk && (
            <span
              className="w-2 h-2 rounded-full bg-critical shrink-0"
              title="Pickup or delivery SLA at risk"
            />
          )}
        </button>
      ),
    },
    {
      id: "lane",
      header: "Origin & Destination",
      cell: (row) => (
        <div className="max-w-[200px]">
          <p className="font-label text-label-md text-on-surface truncate">
            {row.origin_city}, {row.origin_state}
          </p>
          <p className="font-body text-body-sm text-on-surface-muted truncate">
            → {row.destination_city}, {row.destination_state}
          </p>
        </div>
      ),
    },
    {
      id: "transporter",
      header: "Transporter",
      cell: (row) => (
        <span className="font-body text-body-sm text-on-surface">
          {row.transporter_name || "Unassigned"}
        </span>
      ),
    },
    {
      id: "pickup",
      header: "Scheduled Pickup",
      cell: (row) => (
        <div className="tabular-nums">
          <span className="font-body text-body-sm text-on-surface">{formatDate(row.scheduled_pickup_time)}</span>
          {row.actual_pickup_time && (
            <p className="font-label text-label-sm text-success">
              Picked up: {formatDate(row.actual_pickup_time)}
            </p>
          )}
        </div>
      ),
    },
    {
      id: "delivery",
      header: "Expected Delivery",
      cell: (row) => (
        <div className="tabular-nums">
          <span className="font-body text-body-sm text-on-surface">{formatDate(row.expected_delivery_time)}</span>
          {row.actual_delivery_time && (
            <p className="font-label text-label-sm text-success">
              Delivered: {formatDate(row.actual_delivery_time)}
            </p>
          )}
        </div>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => <StatusBadge status={row.status} size="sm" />,
    },
  ];

  // Exceptions columns for Data Table
  const exceptionColumns: ColumnDef<DashboardExceptionItem>[] = [
    {
      id: "tracking_number",
      header: "Shipment Ref",
      cell: (row) => (
        <button
          onClick={() => handleOpenDetail(row.shipment_id)}
          className="font-mono text-mono-sm font-semibold text-primary hover:text-burnt-orange hover:underline flex items-center gap-1.5 cursor-pointer"
        >
          {row.tracking_number}
        </button>
      ),
    },
    {
      id: "title",
      header: "Incident Title",
      cell: (row) => (
        <div className="max-w-[260px]">
          <p className="font-label text-label-md text-on-surface truncate">{row.title}</p>
          <p className="font-body text-body-sm text-on-surface-muted truncate">{row.description}</p>
        </div>
      ),
    },
    {
      id: "severity",
      header: "Severity",
      cell: (row) => <StatusBadge status={row.severity} size="sm" />,
    },
    {
      id: "status",
      header: "Resolution State",
      cell: (row) => <StatusBadge status={row.status} size="sm" />,
    },
    {
      id: "reported_at",
      header: "Reported",
      cell: (row) => (
        <span className="font-mono text-mono-sm text-on-surface-muted tabular-nums">{formatDate(row.reported_at)}</span>
      ),
    },
  ];

  const m = overview?.metrics;

  return (
    <div className="space-y-6">
      {/* Page Header with Real Controls */}
      <PageHeader
        title="Operations Dashboard"
        subtitle={`Live outbound commitment overview · ${user?.organization_name || "Enterprise Freight Command"}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {/* Date Range Preset */}
            <select
              value={datePreset}
              onChange={(e) => setDatePreset(e.target.value)}
              className="font-label text-label-md text-on-surface bg-surface-card border border-outline-strong rounded-sm px-3 py-1.5 outline-none focus:border-burnt-orange"
            >
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
              <option value="90d">Last 90 Days</option>
              <option value="ALL">All Time</option>
            </select>

            {/* Carrier Filter */}
            <select
              value={selectedTransporterId}
              onChange={(e) => setSelectedTransporterId(e.target.value)}
              className="font-label text-label-md text-on-surface bg-surface-card border border-outline-strong rounded-sm px-3 py-1.5 outline-none focus:border-burnt-orange max-w-[180px]"
            >
              <option value="">All Transporters</option>
              {overview?.transporter_rankings?.map((carrier) => (
                <option key={carrier.transporter_id} value={carrier.transporter_id}>
                  {carrier.transporter_name} ({carrier.transporter_code})
                </option>
              ))}
            </select>

            {/* Refresh */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                fetchOverview(true);
                fetchTableData();
              }}
              disabled={overviewLoading || tableLoading}
              className="gap-1.5"
            >
              <RefreshCw className={`h-4 w-4 ${overviewLoading ? "animate-spin" : ""}`} />
              Sync
            </Button>

            {/* Create Shipment Primary CTA */}
            <Button
              variant="default"
              size="sm"
              onClick={() => navigate("/shipments/create")}
              className="gap-1.5"
            >
              <span className="material-symbols-outlined text-[16px]" aria-hidden="true">
                add
              </span>
              Create Shipment
            </Button>
          </div>
        }
      />

      {/* 9 Core Dashboard Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
        <MetricCard
          title="Total Shipments"
          value={m?.total_shipments ?? 0}
          loading={overviewLoading}
          icon={<Package className="h-4 w-4" />}
          accentColor="blue"
        />
        <MetricCard
          title="Pending Pickups"
          value={m?.pending_pickups ?? 0}
          loading={overviewLoading}
          icon={<Clock className="h-4 w-4" />}
          accentColor="blue"
        />
        <MetricCard
          title="Confirmed Bookings"
          value={m?.confirmed_bookings ?? 0}
          loading={overviewLoading}
          icon={<CalendarDays className="h-4 w-4" />}
          accentColor="teal"
        />
        <MetricCard
          title="Pickups at Risk"
          value={m?.pickups_at_risk ?? 0}
          loading={overviewLoading}
          icon={<AlertTriangle className="h-4 w-4" />}
          accentColor="amber"
        />
        <MetricCard
          title="Failed Pickups"
          value={m?.failed_pickups ?? 0}
          loading={overviewLoading}
          icon={<AlertTriangle className="h-4 w-4 text-critical" />}
          accentColor="rose"
        />
        <MetricCard
          title="In-Transit Freight"
          value={m?.in_transit_shipments ?? 0}
          loading={overviewLoading}
          icon={<Truck className="h-4 w-4" />}
          accentColor="blue"
        />
        <MetricCard
          title="Delayed Deliveries"
          value={m?.delayed_deliveries ?? 0}
          loading={overviewLoading}
          icon={<Clock className="h-4 w-4 text-warning" />}
          accentColor="amber"
        />
        <MetricCard
          title="Delivered Shipments"
          value={m?.delivered_shipments ?? 0}
          loading={overviewLoading}
          icon={<CheckCircle2 className="h-4 w-4 text-success" />}
          accentColor="teal"
        />
        <MetricCard
          title="Open Exceptions"
          value={m?.open_exceptions ?? 0}
          loading={overviewLoading}
          icon={<AlertTriangle className="h-4 w-4" />}
          accentColor="rose"
        />
        <MetricCard
          title="Pickup SLA Rate"
          value={`${m?.pickup_success_rate ?? 0}%`}
          loading={overviewLoading}
          icon={<Radio className="h-4 w-4 text-success" />}
          accentColor="teal"
        />
      </div>

      {/* Primary Visualizations: Volume Over Time & Exception Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-8">
          <VolumeOverTimeChart
            data={overview?.volume_over_time || []}
            isLoading={overviewLoading}
          />
        </div>
        <div className="lg:col-span-4">
          <ExceptionDistributionWidget
            types={overview?.exceptions_by_type || []}
            severities={overview?.exceptions_by_severity || []}
          />
        </div>
      </div>

      {/* Secondary Visualizations: Gauges & Leaderboard */}
      {overview && (
        <PerformanceGauges
          pickupPerf={overview.pickup_performance}
          deliveryPerf={overview.delivery_performance}
          transporterRankings={overview.transporter_rankings}
          onSelectTransporter={(tId) => setSelectedTransporterId(tId)}
          selectedTransporterId={selectedTransporterId}
        />
      )}

      {/* Operational Data Tables Section with Tabs */}
      <div className="bg-surface-card rounded-DEFAULT border border-outline-variant p-5 space-y-4">
        {/* Table Tabs & Search */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-3 border-b border-outline-variant">
          {/* Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0">
            <button
              onClick={() => setActiveTab("attention")}
              className={`px-3 py-1.5 rounded-sm font-label text-label-md transition-colors duration-state-change cursor-pointer flex items-center gap-1.5 shrink-0 ${
                activeTab === "attention"
                  ? "bg-critical-container text-on-critical-container border border-critical/20"
                  : "text-on-surface-muted hover:bg-surface-container-low"
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5 text-critical" />
              Requires Attention
            </button>

            <button
              onClick={() => setActiveTab("upcoming")}
              className={`px-3 py-1.5 rounded-sm font-label text-label-md transition-colors duration-state-change cursor-pointer flex items-center gap-1.5 shrink-0 ${
                activeTab === "upcoming"
                  ? "bg-primary-container text-on-primary-container border border-burnt-orange/30"
                  : "text-on-surface-muted hover:bg-surface-container-low"
              }`}
            >
              <Clock className="w-3.5 h-3.5 text-primary" />
              Upcoming Pickups
            </button>

            <button
              onClick={() => setActiveTab("failed")}
              className={`px-3 py-1.5 rounded-sm font-label text-label-md transition-colors duration-state-change cursor-pointer flex items-center gap-1.5 shrink-0 ${
                activeTab === "failed"
                  ? "bg-warning-container text-on-warning-container border border-warning/30"
                  : "text-on-surface-muted hover:bg-surface-container-low"
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5 text-warning" />
              Failed Pickups
            </button>

            <button
              onClick={() => setActiveTab("exceptions")}
              className={`px-3 py-1.5 rounded-sm font-label text-label-md transition-colors duration-state-change cursor-pointer flex items-center gap-1.5 shrink-0 ${
                activeTab === "exceptions"
                  ? "bg-secondary-container text-on-secondary-container border border-outline-strong"
                  : "text-on-surface-muted hover:bg-surface-container-low"
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5 text-secondary" />
              Open Exceptions
            </button>

            <button
              onClick={() => setActiveTab("deliveries")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors cursor-pointer flex items-center gap-1.5 shrink-0 ${
                activeTab === "deliveries"
                  ? "bg-success-container text-teal-800 border border-teal-200"
                  : "text-on-surface-muted hover:bg-surface-container"
              }`}
            >
              <CheckCircle2 className="w-3.5 h-3.5 text-success" />
              Recent Deliveries
            </button>
          </div>

          {/* Search Input */}
          <div className="w-full md:w-64">
            <SearchBar
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder="Search ref, city, lane..."
            />
          </div>
        </div>

        {/* Tab Data Table */}
        {activeTab === "exceptions" ? (
          <div className="space-y-4">
            <DataTable
              columns={exceptionColumns}
              data={exceptionsData?.items || []}
              keyExtractor={(r) => r.id}
              isLoading={tableLoading}
              emptyTitle="No open exceptions"
              emptyDescription="All operational shipments are progressing nominal."
            />
            {exceptionsData && exceptionsData.total > 0 && (
              <Pagination
                currentPage={currentPage}
                totalPages={exceptionsData.total_pages}
                pageSize={pageSize}
                totalItems={exceptionsData.total}
                onPageChange={setCurrentPage}
                onPageSizeChange={setPageSize}
              />
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <DataTable
              columns={shipmentColumns}
              data={shipmentsData?.items || []}
              keyExtractor={(r) => r.id}
              isLoading={tableLoading}
              onRowClick={(row) => handleOpenDetail(row.id)}
              emptyTitle="No shipments in this view"
              emptyDescription="No shipments match the selected operational tab or active filters."
            />
            {shipmentsData && shipmentsData.total > 0 && (
              <Pagination
                currentPage={currentPage}
                totalPages={shipmentsData.total_pages}
                pageSize={pageSize}
                totalItems={shipmentsData.total}
                onPageChange={setCurrentPage}
                onPageSizeChange={setPageSize}
              />
            )}
          </div>
        )}
      </div>

      {/* Live Recent Shipment Activity Stream */}
      {overview?.recent_activity && overview.recent_activity.length > 0 && (
        <div className="bg-surface-card rounded-xl border border-outline-variant shadow-xs p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-outline-variant">
            <div>
              <h3 className="text-sm font-bold text-on-surface">Recent Shipment Activity</h3>
              <p className="text-xs text-on-surface-muted">
                Cryptographic immutable ledger events recorded across all active consignments.
              </p>
            </div>
            <span className="text-[11px] font-bold text-on-success-container bg-success-container px-2 py-0.5 rounded-full border border-teal-200 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-success-container0 animate-pulse" />
              Live Telemetry
            </span>
          </div>

          <div className="space-y-2 max-h-56 overflow-y-auto divide-y divide-outline-variant">
            {overview.recent_activity.map((act) => (
              <div key={act.id} className="pt-2 pb-1 text-xs flex items-start justify-between gap-4">
                <div className="flex items-start gap-2.5 min-w-0">
                  <div className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-on-surface">
                      <button
                        onClick={() => handleOpenDetail(act.shipment_id)}
                        className="text-primary hover:underline font-bold mr-1.5"
                      >
                        {act.tracking_number}
                      </button>
                      &bull; {act.description}
                    </p>
                    <p className="text-[11px] text-on-surface-subtle">
                      Type: {act.event_type} &bull; Source: {act.source}
                      {act.location_name && ` &bull; ${act.location_name}`}
                    </p>
                  </div>
                </div>
                <span className="text-[11px] font-mono text-on-surface-muted shrink-0">
                  {formatDate(act.occurred_at)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Shipment Detail Modal Drawer */}
      <ShipmentDetailModal
        isOpen={isModalOpen}
        shipmentId={selectedShipmentId}
        onClose={() => setIsModalOpen(false)}
      />
    </div>
  );
};
