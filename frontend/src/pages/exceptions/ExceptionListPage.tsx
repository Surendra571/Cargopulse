import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Search,
  Plus,
  ShieldAlert,
  Clock,
  CheckCircle2,
  Eye,
  Check,
  Building2,
  Truck,
} from "lucide-react";
import {
  exceptionsApi,
  ExceptionRecord,
  ExceptionType,
  ExceptionSeverity,
  ExceptionPriority,
} from "@/api/exceptions";
import { PageHeader } from "@/components/common/PageHeader";
import { DataTable, ColumnDef } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/StatusBadge";
import { MetricCard } from "@/components/common/MetricCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/ConfirmationDialog";
import { useToast } from "@/context/ToastContext";

const STATUS_TABS: { label: string; value: string }[] = [
  { label: "All Incidents", value: "ALL" },
  { label: "Open", value: "OPEN" },
  { label: "Acknowledged", value: "ACKNOWLEDGED" },
  { label: "Investigating", value: "INVESTIGATING" },
  { label: "Resolving", value: "RESOLVING" },
  { label: "Resolved", value: "RESOLVED" },
  { label: "Closed", value: "CLOSED" },
];

const EXCEPTION_TYPES: { label: string; value: ExceptionType }[] = [
  { label: "Pickup Overdue", value: "PICKUP_OVERDUE" },
  { label: "Booking Rejected", value: "BOOKING_REJECTED" },
  { label: "Booking Expired", value: "BOOKING_EXPIRED" },
  { label: "Vehicle Unavailable", value: "VEHICLE_UNAVAILABLE" },
  { label: "Tracking Stale", value: "TRACKING_STALE" },
  { label: "Delivery Delayed", value: "DELIVERY_DELAYED" },
  { label: "POD Missing", value: "POD_MISSING" },
  { label: "Delivery Discrepancy", value: "DELIVERY_DISCREPANCY" },
  { label: "Webhook Failure", value: "WEBHOOK_FAILURE" },
  { label: "Integration Failure", value: "INTEGRATION_FAILURE" },
];

export const ExceptionListPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [severityFilter, setSeverityFilter] = useState("ALL");
  const [typeFilter, setTypeFilter] = useState("ALL");

  // Create Modal State
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [selectedType, setSelectedType] = useState<ExceptionType>("PICKUP_OVERDUE");
  const [selectedSeverity, setSelectedSeverity] = useState<ExceptionSeverity>("MEDIUM");
  const [selectedPriority, setSelectedPriority] = useState<ExceptionPriority>("MEDIUM");
  const [shipmentId, setShipmentId] = useState("");
  const [transporterId, setTransporterId] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Query exceptions
  const { data: listData, isLoading } = useQuery({
    queryKey: ["exceptions", page, pageSize, debouncedSearch, statusFilter, severityFilter, typeFilter],
    queryFn: () =>
      exceptionsApi.listExceptions({
        page,
        page_size: pageSize,
        search: debouncedSearch || undefined,
        status: statusFilter !== "ALL" ? statusFilter : undefined,
        severity: severityFilter !== "ALL" ? severityFilter : undefined,
        exception_type: typeFilter !== "ALL" ? typeFilter : undefined,
      }),
    refetchInterval: 15000,
  });

  // Query metrics
  const { data: metrics } = useQuery({
    queryKey: ["exception-metrics"],
    queryFn: () => exceptionsApi.getMetrics(),
    refetchInterval: 30000,
  });

  // Acknowledge mutation
  const acknowledgeMutation = useMutation({
    mutationFn: (id: string) => exceptionsApi.acknowledgeException(id, "Acknowledged from incident control tower"),
    onSuccess: (res) => {
      toast.success("Incident Acknowledged", `Exception ${res.title} is now under management.`);
      queryClient.invalidateQueries({ queryKey: ["exceptions"] });
      queryClient.invalidateQueries({ queryKey: ["exception-metrics"] });
    },
    onError: (err: any) => {
      toast.error("Action Failed", err.response?.data?.detail || "Could not acknowledge incident");
    },
  });

  // Create manual exception mutation
  const createMutation = useMutation({
    mutationFn: () =>
      exceptionsApi.createException({
        title,
        description,
        exception_type: selectedType,
        severity: selectedSeverity,
        priority: selectedPriority,
        shipment_id: shipmentId.trim() || undefined,
        transporter_id: transporterId.trim() || undefined,
      }),
    onSuccess: (res) => {
      toast.success("Incident Logged", `Exception "${res.title}" has been recorded.`);
      setCreateModalOpen(false);
      resetCreateForm();
      queryClient.invalidateQueries({ queryKey: ["exceptions"] });
      queryClient.invalidateQueries({ queryKey: ["exception-metrics"] });
    },
    onError: (err: any) => {
      toast.error("Creation Failed", err.response?.data?.detail || "Could not log exception");
    },
  });

  const resetCreateForm = () => {
    setTitle("");
    setDescription("");
    setSelectedType("PICKUP_OVERDUE");
    setSelectedSeverity("MEDIUM");
    setSelectedPriority("MEDIUM");
    setShipmentId("");
    setTransporterId("");
  };

  const exceptions = listData?.items || [];
  const totalExceptions = listData?.total || 0;
  const totalPages = listData?.pages || 1;

  const columns: ColumnDef<ExceptionRecord>[] = [
    {
      id: "title",
      header: "Incident Details",
      cell: (exc) => (
        <div className="flex flex-col">
          <Link
            to={`/exceptions/${exc.id}`}
            className="font-semibold text-primary hover:text-burnt-orange hover:underline flex items-center gap-1.5"
          >
            {exc.title}
          </Link>
          <span className="text-xs text-on-surface-muted line-clamp-1 mt-0.5">{exc.description}</span>
          <span className="text-[11px] font-mono text-on-surface-subtle mt-0.5">ID: {exc.id.slice(0, 8)}</span>
        </div>
      ),
    },
    {
      id: "type",
      header: "Exception Type",
      cell: (exc) => (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-surface-container text-on-surface border border-outline-variant">
          {exc.exception_type.replace(/_/g, " ")}
        </span>
      ),
    },
    {
      id: "severity_priority",
      header: "Severity / Priority",
      cell: (exc) => (
        <div className="flex flex-col gap-1 items-start">
          <StatusBadge status={exc.severity} size="sm" />
          <span className="text-[11px] text-on-surface-muted font-medium">Priority: {exc.priority}</span>
        </div>
      ),
    },
    {
      id: "related_dossier",
      header: "Related Dossier",
      cell: (exc) => (
        <div className="flex flex-col text-xs space-y-0.5">
          {exc.shipment ? (
            <Link
              to={`/shipments/${exc.shipment_id}`}
              className="text-primary hover:underline flex items-center gap-1 font-mono"
            >
              <Truck className="h-3 w-3 text-on-surface-subtle" />
              {exc.shipment.tracking_number}
            </Link>
          ) : (
            <span className="text-on-surface-subtle italic">No linked shipment</span>
          )}

          {exc.transporter ? (
            <span className="text-on-surface flex items-center gap-1">
              <Building2 className="h-3 w-3 text-on-surface-subtle" />
              {exc.transporter.name}
            </span>
          ) : null}
        </div>
      ),
    },
    {
      id: "reported_at",
      header: "Reported At",
      cell: (exc) => (
        <div className="flex flex-col text-xs text-on-surface-muted">
          <span className="font-medium">{new Date(exc.reported_at).toLocaleDateString()}</span>
          <span className="text-on-surface-subtle text-[11px]">{new Date(exc.reported_at).toLocaleTimeString()}</span>
        </div>
      ),
    },
    {
      id: "assigned_coordinator",
      header: "Assigned Coordinator",
      cell: (exc) => (
        <span className="text-xs text-on-surface">
          {exc.assigned_owner ? exc.assigned_owner.full_name : <span className="text-on-surface-subtle italic">Unassigned</span>}
        </span>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: (exc) => <StatusBadge status={exc.status} />,
    },
    {
      id: "actions",
      header: "Actions",
      cell: (exc) => (
        <div className="flex items-center gap-2">
          {exc.status === "OPEN" && (
            <Button
              size="sm"
              variant="outline"
              className="text-xs h-7 px-2 border-amber-300 text-amber-800 hover:bg-warning-container"
              onClick={() => acknowledgeMutation.mutate(exc.id)}
              disabled={acknowledgeMutation.isPending}
            >
              <Check className="h-3 w-3 mr-1" />
              Acknowledge
            </Button>
          )}
          <Link to={`/exceptions/${exc.id}`}>
            <Button size="sm" variant="ghost" className="text-xs h-7 px-2 text-on-surface-muted hover:text-primary">
              <Eye className="h-3.5 w-3.5 mr-1" />
              Dossier
            </Button>
          </Link>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title="Exception Management Control Tower"
        subtitle="Continuous operational triage, multi-tiered severity routing, SLA breach diagnostics, and closure audits."
        breadcrumbs={[
          { label: "Overview", href: "/overview" },
          { label: "Exceptions" },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="default"
              size="sm"
              onClick={() => setCreateModalOpen(true)}
              className="bg-navy-900 hover:bg-navy-800 text-white shadow-2xs"
            >
              <Plus className="h-4 w-4 mr-1.5" />
              Report Incident
            </Button>
          </div>
        }
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Incidents"
          value={metrics?.total_exceptions ?? totalExceptions}
          icon={<ShieldAlert className="h-5 w-5 text-primary" />}
          footnote="Lifetime operational events"
        />
        <MetricCard
          title="Active / In-Triage"
          value={metrics?.open_exceptions ?? 0}
          icon={<Clock className="h-5 w-5 text-amber-500" />}
          footnote="Open &amp; investigating cases"
        />
        <MetricCard
          title="Critical Severity"
          value={metrics?.critical_count ?? 0}
          icon={<AlertTriangle className="h-5 w-5 text-critical" />}
          footnote="Immediate attention required"
        />
        <MetricCard
          title="Mean Resolution Time"
          value={`${metrics?.mean_resolution_hours ? metrics.mean_resolution_hours.toFixed(1) : "0.0"} hrs`}
          icon={<CheckCircle2 className="h-5 w-5 text-success" />}
          footnote="Time to resolution"
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

      {/* Filter & Search Bar */}
      <Card className="p-4 space-y-4">
        <div className="flex flex-col md:flex-row gap-3 items-center justify-between">
          <div className="relative w-full md:w-96">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-on-surface-subtle" />
            <Input
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search title, description, or reference..."
              className="pl-9 text-xs"
            />
          </div>

          <div className="flex items-center gap-2 w-full md:w-auto">
            {/* Severity Filter */}
            <select
              value={severityFilter}
              onChange={(e) => {
                setSeverityFilter(e.target.value);
                setPage(1);
              }}
              className="text-xs border rounded-lg px-2.5 py-1.5 bg-surface-card text-on-surface border-outline-variant"
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>

            {/* Type Filter */}
            <select
              value={typeFilter}
              onChange={(e) => {
                setTypeFilter(e.target.value);
                setPage(1);
              }}
              className="text-xs border rounded-lg px-2.5 py-1.5 bg-surface-card text-on-surface border-outline-variant"
            >
              <option value="ALL">All Incident Types</option>
              {EXCEPTION_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <DataTable
          columns={columns}
          data={exceptions}
          keyExtractor={(item) => item.id}
          isLoading={isLoading}
          pagination={{
            currentPage: page,
            totalPages,
            totalItems: totalExceptions,
            pageSize,
            onPageChange: setPage,
          }}
          emptyTitle="No exceptions found"
          emptyDescription="No operational exceptions matching the active filters."
        />
      </Card>

      {/* Manual Report Modal */}
      <ConfirmationDialog
        isOpen={createModalOpen}
        onClose={() => {
          setCreateModalOpen(false);
          resetCreateForm();
        }}
        onConfirm={() => {
          if (!title.trim() || !description.trim()) {
            toast.error("Required Fields", "Please provide both incident title and description.");
            return;
          }
          createMutation.mutate();
        }}
        title="Report Operational Incident / Exception"
        description="Log an unforeseen operational discrepancy, carrier failure, or dispatch breakdown into the system audit trail."
        confirmLabel="Submit Incident"
        isLoading={createMutation.isPending}
      >
        <div className="space-y-3 mt-3 max-h-[60vh] overflow-y-auto pr-1">
          <div>
            <label className="text-xs font-semibold text-on-surface">Incident Title *</label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Origin Dock Congestion - Driver Turned Away"
              className="mt-1 text-xs"
            />
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="text-xs font-semibold text-on-surface">Type *</label>
              <select
                value={selectedType}
                onChange={(e) => setSelectedType(e.target.value as ExceptionType)}
                className="w-full mt-1 text-xs border rounded-md p-1.5 bg-surface-card border-outline-variant"
              >
                {EXCEPTION_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-on-surface">Severity *</label>
              <select
                value={selectedSeverity}
                onChange={(e) => setSelectedSeverity(e.target.value as ExceptionSeverity)}
                className="w-full mt-1 text-xs border rounded-md p-1.5 bg-surface-card border-outline-variant"
              >
                <option value="CRITICAL">Critical</option>
                <option value="HIGH">High</option>
                <option value="MEDIUM">Medium</option>
                <option value="LOW">Low</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-on-surface">Priority *</label>
              <select
                value={selectedPriority}
                onChange={(e) => setSelectedPriority(e.target.value as ExceptionPriority)}
                className="w-full mt-1 text-xs border rounded-md p-1.5 bg-surface-card border-outline-variant"
              >
                <option value="CRITICAL">Critical</option>
                <option value="HIGH">High</option>
                <option value="MEDIUM">Medium</option>
                <option value="LOW">Low</option>
              </select>
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-on-surface">Description *</label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Detailed operational breakdown and current ground situation..."
              className="w-full mt-1 text-xs border rounded-md p-2 bg-surface-card border-outline-variant"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs font-semibold text-on-surface">Shipment ID (Optional UUID)</label>
              <Input
                value={shipmentId}
                onChange={(e) => setShipmentId(e.target.value)}
                placeholder="Optional shipment UUID"
                className="mt-1 text-xs"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-on-surface">Transporter ID (Optional UUID)</label>
              <Input
                value={transporterId}
                onChange={(e) => setTransporterId(e.target.value)}
                placeholder="Optional carrier UUID"
                className="mt-1 text-xs"
              />
            </div>
          </div>
        </div>
      </ConfirmationDialog>
    </div>
  );
};
