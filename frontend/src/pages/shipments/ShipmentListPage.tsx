import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Search,
  Filter,
  Eye,
  Edit2,
  XCircle,
  Truck,
  Clock,
  AlertTriangle,
  ArrowRight,
  RefreshCw,
} from "lucide-react";
import { shipmentApi, ShipmentListItem, ShipmentListParams } from "@/api/shipments";
import { PageHeader } from "@/components/common/PageHeader";
import { DataTable, ColumnDef } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/ConfirmationDialog";
import { useToast } from "@/context/ToastContext";

export const ShipmentListPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [priorityFilter, setPriorityFilter] = useState("ALL");

  // Cancel dialog state
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [selectedShipmentToCancel, setSelectedShipmentToCancel] = useState<ShipmentListItem | null>(null);
  const [cancellationReason, setCancellationReason] = useState("");

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const queryParams: ShipmentListParams = {
    page,
    page_size: pageSize,
    search: debouncedSearch || undefined,
    status: statusFilter !== "ALL" ? statusFilter : undefined,
    priority: priorityFilter !== "ALL" ? priorityFilter : undefined,
  };

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["shipments", queryParams],
    queryFn: () => shipmentApi.listShipments(queryParams),
  });

  const cancelMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      shipmentApi.cancelShipment(id, { cancellation_reason: reason }),
    onSuccess: (updated) => {
      toast.success(
        "Shipment Cancelled",
        `Shipment ${updated.tracking_number} has been cancelled.`
      );
      setCancelModalOpen(false);
      setSelectedShipmentToCancel(null);
      setCancellationReason("");
      queryClient.invalidateQueries({ queryKey: ["shipments"] });
    },
    onError: (err: any) => {
      const msg = err.response?.data?.detail || "Failed to cancel shipment.";
      toast.error("Cancellation Error", msg);
    },
  });

  const handleOpenCancel = (shipment: ShipmentListItem) => {
    setSelectedShipmentToCancel(shipment);
    setCancellationReason("");
    setCancelModalOpen(true);
  };

  const handleConfirmCancel = () => {
    if (!selectedShipmentToCancel) return;
    if (!cancellationReason.trim()) {
      toast.warning("Reason Required", "Please provide a valid cancellation reason.");
      return;
    }
    cancelMutation.mutate({
      id: selectedShipmentToCancel.id,
      reason: cancellationReason.trim(),
    });
  };

  const columns: ColumnDef<ShipmentListItem>[] = [
    {
      id: "tracking_number",
      header: "Shipment Ref",
      cell: (row) => (
        <div className="flex flex-col">
          <span
            onClick={() => navigate(`/shipments/${row.id}`)}
            className="font-mono text-xs font-bold text-primary hover:text-burnt-orange hover:underline cursor-pointer"
          >
            {row.tracking_number}
          </span>
          <span className="text-[11px] text-on-surface-muted font-medium">
            {row.customer_name || "Direct Shipper"}
          </span>
        </div>
      ),
    },
    {
      id: "lane",
      header: "Origin & Destination",
      cell: (row) => (
        <div className="flex items-center gap-2 text-xs text-on-surface">
          <div className="flex flex-col">
            <span className="font-semibold text-on-surface">{row.origin_city}, {row.origin_state}</span>
            <span className="text-[10px] text-on-surface-subtle truncate max-w-[120px]">{row.origin_name}</span>
          </div>
          <ArrowRight className="h-3 w-3 text-on-surface-subtle shrink-0" />
          <div className="flex flex-col">
            <span className="font-semibold text-on-surface">{row.destination_city}, {row.destination_state}</span>
            <span className="text-[10px] text-on-surface-subtle truncate max-w-[120px]">{row.destination_name}</span>
          </div>
        </div>
      ),
    },
    {
      id: "schedule",
      header: "Pickup Deadline / ETA",
      cell: (row) => (
        <div className="flex flex-col text-xs text-on-surface-muted">
          <div className="flex items-center gap-1">
            <Clock className="h-3 w-3 text-amber-500" />
            <span className="font-medium text-on-surface">
              {new Date(row.scheduled_pickup_time).toLocaleDateString([], {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          </div>
          <span className="text-[11px] text-on-surface-subtle mt-0.5">
            ETA:{" "}
            {new Date(row.expected_delivery_time).toLocaleDateString([], {
              month: "short",
              day: "numeric",
            })}
          </span>
        </div>
      ),
    },
    {
      id: "cargo",
      header: "Cargo & Specs",
      cell: (row) => (
        <div className="flex flex-col text-xs">
          <span className="font-medium text-on-surface">
            {row.total_weight_kg.toLocaleString()} kg
          </span>
          <span className="text-[11px] text-on-surface-muted">
            {row.package_count} {row.package_unit.toLowerCase()} • {row.cargo_category.replace(/_/g, " ")}
          </span>
        </div>
      ),
    },
    {
      id: "carrier",
      header: "Assigned Carrier",
      cell: (row) => (
        <div className="flex items-center gap-1.5 text-xs">
          <Truck className="h-3.5 w-3.5 text-on-surface-subtle shrink-0" />
          <span className="font-medium text-on-surface">
            {row.assigned_transporter_name || (
              <span className="text-on-surface-subtle italic">Unassigned</span>
            )}
          </span>
        </div>
      ),
    },
    {
      id: "priority",
      header: "Priority",
      cell: (row) => {
        const p = row.priority?.toUpperCase();
        let color = "bg-surface-container text-on-surface border-outline-variant";
        if (p === "CRITICAL") color = "bg-critical-container text-on-critical-container border-rose-200 font-semibold";
        if (p === "EXPEDITED") color = "bg-warning-container text-on-warning-container border-amber-200 font-semibold";
        return (
          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] border ${color}`}>
            {p || "STANDARD"}
          </span>
        );
      },
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => (
        <div className="flex flex-col gap-1 items-start">
          <StatusBadge status={row.status} />
          {row.open_exceptions_count > 0 && (
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-critical bg-critical-container px-1.5 py-0.5 rounded border border-rose-200">
              <AlertTriangle className="h-2.5 w-2.5" />
              {row.open_exceptions_count} Exception{row.open_exceptions_count > 1 ? "s" : ""}
            </span>
          )}
        </div>
      ),
    },
    {
      id: "actions",
      header: "Actions",
      align: "right",
      cell: (row) => {
        const canEdit = ["DRAFT", "PENDING_ACCEPTANCE", "COMMITTED"].includes(row.status);
        const canCancel = !["DELIVERED", "CANCELLED"].includes(row.status);

        return (
          <div className="flex items-center justify-end gap-1.5">
            <Button
              variant="outline"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                navigate(`/shipments/${row.id}`);
              }}
              className="h-7 px-2 text-xs text-on-surface hover:text-primary hover:border-blue-300"
              title="View Shipment Details"
            >
              <Eye className="h-3.5 w-3.5 mr-1" />
              View
            </Button>

            {canEdit && (
              <Button
                variant="outline"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  navigate(`/shipments/${row.id}/edit`);
                }}
                className="h-7 px-2 text-xs text-on-surface hover:text-warning hover:border-amber-300"
                title="Edit Shipment"
              >
                <Edit2 className="h-3.5 w-3.5 mr-1" />
                Edit
              </Button>
            )}

            {canCancel && (
              <Button
                variant="outline"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  handleOpenCancel(row);
                }}
                className="h-7 px-2 text-xs text-critical hover:text-on-critical-container hover:bg-critical-container hover:border-rose-300"
                title="Cancel Shipment"
              >
                <XCircle className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        );
      },
    },
  ];

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Top Header */}
      <PageHeader
        title="Shipment Management"
        subtitle="Create outbound freight shipments, monitor transit milestones, assign transporters, and maintain immutable audit histories."
        breadcrumbs={[
          { label: "Dashboard", href: "/overview" },
          { label: "Shipments", href: "/shipments" },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              className="h-9 gap-1.5 text-xs text-on-surface-muted"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Refresh
            </Button>
            <Button
              onClick={() => navigate("/shipments/create")}
              className="h-9 gap-1.5 text-xs bg-primary hover:bg-burnt-orange text-white font-semibold shadow-xs"
            >
              <Plus className="h-4 w-4" />
              Create Shipment
            </Button>
          </div>
        }
      />

      {/* Filter and Search Bar */}
      <Card className="p-4 bg-surface-card border-outline-variant shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-on-surface-subtle" />
            <Input
              type="text"
              placeholder="Search by shipment ref, customer, origin, or goods..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 text-xs h-9"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 text-xs text-on-surface-muted">
              <Filter className="h-3.5 w-3.5 text-on-surface-subtle" />
              <span className="font-medium">Status:</span>
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                className="text-xs bg-surface-container-low border border-outline-variant rounded-md px-2 py-1 text-on-surface focus:outline-hidden focus:ring-1 focus:ring-burnt-orange"
              >
                <option value="ALL">All Statuses</option>
                <option value="DRAFT">Draft</option>
                <option value="COMMITTED">Committed</option>
                <option value="DISPATCHED">Dispatched</option>
                <option value="AT_PICKUP">At Pickup</option>
                <option value="IN_TRANSIT">In Transit</option>
                <option value="DELIVERED">Delivered</option>
                <option value="CANCELLED">Cancelled</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5 text-xs text-on-surface-muted ml-2">
              <span className="font-medium">Priority:</span>
              <select
                value={priorityFilter}
                onChange={(e) => {
                  setPriorityFilter(e.target.value);
                  setPage(1);
                }}
                className="text-xs bg-surface-container-low border border-outline-variant rounded-md px-2 py-1 text-on-surface focus:outline-hidden focus:ring-1 focus:ring-burnt-orange"
              >
                <option value="ALL">All Priorities</option>
                <option value="STANDARD">Standard</option>
                <option value="EXPEDITED">Expedited</option>
                <option value="CRITICAL">Critical</option>
              </select>
            </div>
          </div>
        </div>
      </Card>

      {/* Main Table */}
      <DataTable
        columns={columns}
        data={data?.items || []}
        keyExtractor={(row) => row.id}
        isLoading={isLoading}
        emptyTitle="No Shipments Found"
        emptyDescription="Create your first outbound shipment or adjust your search filters."
        emptyActionLabel="Create Shipment"
        onEmptyAction={() => navigate("/shipments/create")}
        onRowClick={(row) => navigate(`/shipments/${row.id}`)}
        pagination={
          data
            ? {
                currentPage: page,
                totalPages: data.total_pages,
                totalItems: data.total,
                pageSize: pageSize,
                onPageChange: (newPage) => setPage(newPage),
              }
            : undefined
        }
      />

      {/* Cancel Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={cancelModalOpen}
        onClose={() => setCancelModalOpen(false)}
        onConfirm={handleConfirmCancel}
        title={`Cancel Shipment ${selectedShipmentToCancel?.tracking_number || ""}`}
        description="Are you sure you want to cancel this shipment? Active carrier bookings and pickup commitments will be invalidated. This action will be recorded in the audit trail."
        confirmLabel="Cancel Shipment"
        variant="destructive"
        isLoading={cancelMutation.isPending}
      >
        <div className="mt-4 space-y-2">
          <label className="text-xs font-semibold text-on-surface">
            Cancellation Reason <span className="text-rose-500">*</span>
          </label>
          <textarea
            value={cancellationReason}
            onChange={(e) => setCancellationReason(e.target.value)}
            placeholder="Specify reason for cancelling this shipment (e.g. customer request, production delay)..."
            rows={3}
            className="w-full text-xs rounded-md border border-outline-variant p-2.5 text-on-surface focus:outline-hidden focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
          />
        </div>
      </ConfirmationDialog>
    </div>
  );
};

export default ShipmentListPage;
