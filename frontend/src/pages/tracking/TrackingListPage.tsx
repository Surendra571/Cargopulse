import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Navigation,
  Search,
  RotateCw,
  AlertTriangle,
  Clock,
  CheckCircle2,
  Truck,
  MapPin,
  Building2,
  Calendar,
  Radio,
} from "lucide-react";
import {
  trackingApi,
  TrackedShipmentItem,
} from "@/api/tracking";
import { PageHeader } from "@/components/common/PageHeader";
import { DataTable, ColumnDef } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/StatusBadge";
import { MetricCard } from "@/components/common/MetricCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { useToast } from "@/context/ToastContext";

const STATUS_TABS: { label: string; value: string }[] = [
  { label: "All Active", value: "ALL" },
  { label: "Committed", value: "COMMITTED" },
  { label: "At Pickup", value: "AT_PICKUP" },
  { label: "Dispatched", value: "DISPATCHED" },
  { label: "In Transit", value: "IN_TRANSIT" },
  { label: "Out for Delivery", value: "OUT_FOR_DELIVERY" },
  { label: "Delivered", value: "DELIVERED" },
];

export const TrackingListPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [staleOnly, setStaleOnly] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const { data, isLoading } = useQuery({
    queryKey: ["tracking-shipments", page, pageSize, debouncedSearch, statusFilter, staleOnly],
    queryFn: () =>
      trackingApi.listTrackedShipments({
        page,
        page_size: pageSize,
        search: debouncedSearch || undefined,
        status: statusFilter !== "ALL" ? statusFilter : undefined,
        is_stale: staleOnly ? true : undefined,
      }),
    refetchInterval: 15000,
  });

  const scanMutation = useMutation({
    mutationFn: () => trackingApi.scanStaleTracking({ threshold_hours: 6 }),
    onSuccess: (res) => {
      toast.success(
        "Surveillance Scan Complete",
        `Scanned ${res.scanned_count} active shipments | Stale flagged: ${res.stale_flagged_count} | Exceptions: ${res.exceptions_created}`
      );
      queryClient.invalidateQueries({ queryKey: ["tracking-shipments"] });
    },
    onError: (err: any) => {
      toast.error("Scan Failed", err.response?.data?.detail || "Could not complete surveillance scan");
    },
  });

  const shipments = data?.items || [];
  const totalShipments = data?.total || 0;
  const totalPages = data?.pages || 1;

  const inTransitCount = shipments.filter(
    (s) => s.status === "IN_TRANSIT" || s.status === "OUT_FOR_DELIVERY"
  ).length;
  const staleCount = shipments.filter((s) => s.is_tracking_stale).length;
  const delayedCount = shipments.filter((s) => s.eta_delay_minutes >= 60).length;

  const columns: ColumnDef<TrackedShipmentItem>[] = [
    {
      id: "shipment",
      header: "Shipment / Ref",
      cell: (item) => (
        <div className="flex flex-col">
          <Link
            to={`/tracking/${item.id}`}
            className="font-mono font-semibold text-primary hover:text-burnt-orange hover:underline flex items-center gap-1.5"
          >
            {item.tracking_number}
            <Radio className="h-3 w-3 text-emerald-500 animate-pulse" />
          </Link>
          <span className="text-xs text-on-surface-muted mt-0.5 font-mono">
            {item.origin_city} &rarr; {item.destination_city}
          </span>
          <span className="text-[11px] text-on-surface-subtle mt-0.5">
            {Math.round(item.total_weight_kg).toLocaleString()} kg
          </span>
        </div>
      ),
    },
    {
      id: "milestone",
      header: "Current Milestone",
      cell: (item) => (
        <div className="flex flex-col items-start gap-1">
          {item.current_milestone ? (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
              {item.current_milestone.replace(/_/g, " ")}
            </span>
          ) : (
            <span className="text-xs text-on-surface-subtle italic">No milestone recorded</span>
          )}
          <StatusBadge status={item.status} size="sm" />
        </div>
      ),
    },
    {
      id: "last_location",
      header: "Last Reported Location",
      cell: (item) => (
        <div className="flex flex-col text-xs space-y-0.5">
          <span className="font-medium text-on-surface flex items-center gap-1">
            <MapPin className="h-3.5 w-3.5 text-on-surface-subtle" />
            {item.last_known_location || "Location Pending"}
          </span>
          {item.last_known_latitude !== null && item.last_known_longitude !== null && (
            <span className="text-[11px] font-mono text-on-surface-subtle">
              {item.last_known_latitude?.toFixed(4)}, {item.last_known_longitude?.toFixed(4)}
            </span>
          )}
          {item.last_tracking_event_at && (
            <span className="text-[10px] text-on-surface-subtle">
              {new Date(item.last_tracking_event_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
        </div>
      ),
    },
    {
      id: "eta",
      header: "Expected Delivery (ETA)",
      cell: (item) => {
        const eta = new Date(item.expected_delivery_time);
        return (
          <div className="flex flex-col text-xs">
            <span className="font-semibold text-on-surface flex items-center gap-1">
              <Calendar className="h-3.5 w-3.5 text-on-surface-subtle" />
              {eta.toLocaleDateString()} {eta.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
            {item.eta_delay_minutes > 0 ? (
              <span className="text-[11px] font-bold text-critical flex items-center gap-0.5 mt-0.5">
                <AlertTriangle className="h-3 w-3" /> +{item.eta_delay_minutes}m Delay
              </span>
            ) : (
              <span className="text-[11px] text-success mt-0.5">On Schedule</span>
            )}
          </div>
        );
      },
    },
    {
      id: "carrier",
      header: "Carrier & Driver",
      cell: (item) => (
        <div className="flex flex-col text-xs space-y-0.5">
          {item.carrier ? (
            <span className="text-on-surface font-medium flex items-center gap-1">
              <Building2 className="h-3.5 w-3.5 text-on-surface-subtle" />
              {item.carrier.name}
            </span>
          ) : (
            <span className="text-on-surface-subtle italic">Unassigned</span>
          )}
          {item.vehicle && (
            <span className="text-on-surface-muted font-mono flex items-center gap-1">
              <Truck className="h-3 w-3 text-on-surface-subtle" />
              {item.vehicle.license_plate}
            </span>
          )}
        </div>
      ),
    },
    {
      id: "stale_status",
      header: "Telemetry Health",
      cell: (item) => (
        <div>
          {item.is_tracking_stale ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold bg-amber-100 text-amber-800 border border-amber-300 animate-pulse">
              <AlertTriangle className="h-3 w-3" /> Stale (&gt;6h)
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-success-container text-on-success-container border border-emerald-200">
              <CheckCircle2 className="h-3 w-3" /> Active Ping
            </span>
          )}
        </div>
      ),
    },
    {
      id: "actions",
      header: "Actions",
      cell: (item) => (
        <Link to={`/tracking/${item.id}`}>
          <Button size="sm" variant="outline" className="text-xs h-7 px-2.5 border-burnt-orange/30 text-primary hover:bg-primary-container">
            <Radio className="h-3 w-3 mr-1 text-primary" />
            Live View
          </Button>
        </Link>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title="Shipment Tracking &amp; Milestones Control Tower"
        subtitle="Centralized telematics feed, 10-milestone chronological roadmap, live WebSockets, and stale telemetry surveillance."
        breadcrumbs={[
          { label: "Overview", href: "/overview" },
          { label: "Tracking" },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="default"
              size="sm"
              onClick={() => scanMutation.mutate()}
              disabled={scanMutation.isPending}
              className="bg-navy-900 hover:bg-navy-800 text-white shadow-2xs"
            >
              <RotateCw className={`h-4 w-4 mr-1.5 ${scanMutation.isPending ? "animate-spin" : ""}`} />
              {scanMutation.isPending ? "Scanning Telemetry..." : "Scan Stale Tracking"}
            </Button>
          </div>
        }
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Tracked Consignments"
          value={totalShipments}
          icon={<Navigation className="h-5 w-5 text-primary" />}
          footnote="Active shipments under tracking"
        />
        <MetricCard
          title="In Transit / Delivery"
          value={inTransitCount}
          icon={<Truck className="h-5 w-5 text-success" />}
          footnote="Actively moving on route"
        />
        <MetricCard
          title="Stale Telemetry"
          value={staleCount}
          icon={<AlertTriangle className="h-5 w-5 text-amber-500" />}
          footnote="No ping in > 6 hours"
        />
        <MetricCard
          title="Delayed Deliveries"
          value={delayedCount}
          icon={<Clock className="h-5 w-5 text-critical" />}
          footnote="Delay exceeds 60 minutes"
        />
      </div>

      {/* Status Filter Tabs */}
      <div className="border-b border-outline-variant">
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => {
                setStatusFilter(tab.value);
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
                statusFilter === tab.value
                  ? "bg-surface-card text-white"
                  : "bg-surface-container text-on-surface-muted hover:bg-surface-container"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Filter and Search Bar */}
      <Card className="p-4 space-y-4">
        <div className="flex flex-col md:flex-row gap-3 items-center justify-between">
          <div className="relative w-full md:w-96">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-on-surface-subtle" />
            <Input
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search tracking number, lane, or location..."
              className="pl-9 text-xs"
            />
          </div>

          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-xs font-medium text-on-surface cursor-pointer select-none">
              <input
                type="checkbox"
                checked={staleOnly}
                onChange={(e) => {
                  setStaleOnly(e.target.checked);
                  setPage(1);
                }}
                className="rounded border-outline-strong text-primary focus:ring-burnt-orange h-3.5 w-3.5"
              />
              Show Stale Telemetry Only
            </label>
          </div>
        </div>

        <DataTable
          columns={columns}
          data={shipments}
          keyExtractor={(item) => item.id}
          isLoading={isLoading}
          pagination={{
            currentPage: page,
            totalPages,
            totalItems: totalShipments,
            pageSize,
            onPageChange: setPage,
          }}
          emptyTitle="No tracked shipments found"
          emptyDescription="No shipments matching active criteria are currently reporting tracking updates."
        />
      </Card>
    </div>
  );
};
