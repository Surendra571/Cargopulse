import React, { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  Search,
  Truck,
  CheckCircle2,
  Clock,
  AlertTriangle,
  XCircle,
  Eye,
  ShieldCheck,
  UserCheck,
  ExternalLink,
} from "lucide-react";
import {
  bookingApi,
  BookingResponse,
  BookingStatus,
  BookingListQueryParams,
} from "@/api/bookings";
import { PageHeader } from "@/components/common/PageHeader";
import { DataTable, ColumnDef } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { MetricCard } from "@/components/common/MetricCard";
import { ConfirmationDialog } from "@/components/common/ConfirmationDialog";
import { useToast } from "@/context/ToastContext";

const STATUS_TABS: { label: string; value: string }[] = [
  { label: "All Tenders", value: "ALL" },
  { label: "Requested", value: "REQUESTED" },
  { label: "Pending Accept", value: "PENDING_ACCEPTANCE" },
  { label: "Accepted", value: "ACCEPTED" },
  { label: "Confirmed", value: "CONFIRMED" },
  { label: "Rejected", value: "REJECTED" },
  { label: "Expired", value: "EXPIRED" },
  { label: "Cancelled", value: "CANCELLED" },
];

export const BookingListPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  // Cancel dialog
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [selectedBookingToCancel, setSelectedBookingToCancel] = useState<BookingResponse | null>(null);
  const [cancellationReason, setCancellationReason] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const queryParams: BookingListQueryParams = {
    page,
    page_size: pageSize,
    search: debouncedSearch || undefined,
    status: statusFilter !== "ALL" ? (statusFilter as BookingStatus) : undefined,
  };

  const { data, isLoading } = useQuery({
    queryKey: ["bookings", queryParams],
    queryFn: () => bookingApi.listBookings(queryParams),
  });

  const cancelMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      bookingApi.cancelBooking(id, { cancellation_reason: reason }),
    onSuccess: (res) => {
      toast.success("Booking Cancelled", `Tender ${res.booking_reference} has been cancelled.`);
      setCancelModalOpen(false);
      setSelectedBookingToCancel(null);
      setCancellationReason("");
      queryClient.invalidateQueries({ queryKey: ["bookings"] });
    },
    onError: (err: any) => {
      toast.error("Cancellation Failed", err.response?.data?.detail || "Could not cancel booking.");
    },
  });

  const handleOpenCancel = (booking: BookingResponse) => {
    setSelectedBookingToCancel(booking);
    setCancellationReason("");
    setCancelModalOpen(true);
  };

  const handleConfirmCancel = () => {
    if (!selectedBookingToCancel) return;
    if (!cancellationReason.trim()) {
      toast.error("Reason Required", "Please provide an operational cancellation reason.");
      return;
    }
    cancelMutation.mutate({
      id: selectedBookingToCancel.id,
      reason: cancellationReason.trim(),
    });
  };

  const bookings = data?.items || [];
  const totalBookings = data?.total || 0;
  const requestedCount = bookings.filter((b) => b.status === "REQUESTED" || b.status === "PENDING_ACCEPTANCE").length;
  const confirmedCount = bookings.filter((b) => b.status === "CONFIRMED").length;
  const expiredOrRejectedCount = bookings.filter((b) => b.status === "EXPIRED" || b.status === "REJECTED").length;

  const columns: ColumnDef<BookingResponse>[] = [
    {
      id: "booking_reference",
      header: "Tender Ref",
      cell: (row) => (
        <div className="flex flex-col">
          <Link
            to={`/bookings/${row.id}`}
            className="font-mono text-sm font-semibold text-primary hover:text-burnt-orange hover:underline flex items-center gap-1"
          >
            {row.booking_reference}
            <ExternalLink className="h-3 w-3 opacity-60" />
          </Link>
          <span className="text-[11px] text-on-surface-subtle">
            {new Date(row.created_at).toLocaleDateString()}
          </span>
        </div>
      ),
    },
    {
      id: "shipment",
      header: "Shipment / Lane",
      cell: (row) => {
        if (!row.shipment) return <span className="text-on-surface-subtle italic">No shipment</span>;
        return (
          <div className="flex flex-col max-w-[220px]">
            <Link
              to={`/shipments/${row.shipment_id}`}
              className="text-xs font-semibold text-on-surface hover:text-primary truncate"
              title={row.shipment.tracking_number}
            >
              {row.shipment.tracking_number}
            </Link>
            <div className="text-[11px] text-on-surface-muted flex items-center gap-1 mt-0.5">
              <span>{row.shipment.origin_city}</span>
              <span className="text-on-surface-muted">→</span>
              <span>{row.shipment.destination_city}</span>
            </div>
            <span className="text-[10px] text-on-surface-subtle font-medium">
              {row.shipment.total_weight_kg.toLocaleString()} kg · {row.shipment.required_vehicle_type}
            </span>
          </div>
        );
      },
    },
    {
      id: "transporter",
      header: "Transporter Carrier",
      cell: (row) => {
        if (!row.transporter) return <span className="text-on-surface-subtle italic">Unassigned</span>;
        return (
          <div className="flex flex-col">
            <Link
              to={`/transporters/${row.transporter_id}`}
              className="text-xs font-semibold text-on-surface hover:text-primary"
            >
              {row.transporter.name}
            </Link>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-surface-container text-on-surface-muted font-mono">
                {row.transporter.code}
              </span>
              <span className="text-[10px] text-success font-medium flex items-center gap-0.5">
                <ShieldCheck className="h-3 w-3" />
                {row.transporter.reliability_score.toFixed(0)}%
              </span>
            </div>
          </div>
        );
      },
    },
    {
      id: "rates",
      header: "Rate (Tariff)",
      cell: (row) => (
        <div className="flex flex-col text-xs">
          {row.agreed_rate !== null && row.agreed_rate !== undefined ? (
            <span className="font-semibold text-on-surface">
              ${row.agreed_rate.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </span>
          ) : row.offered_rate !== null && row.offered_rate !== undefined ? (
            <span className="text-on-surface-muted">
              Offered: ${row.offered_rate.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </span>
          ) : (
            <span className="text-on-surface-subtle italic">Tariff quote</span>
          )}
          {row.agreed_rate && row.offered_rate && row.agreed_rate !== row.offered_rate && (
            <span className="text-[10px] text-on-surface-subtle">
              Orig: ${row.offered_rate.toFixed(0)}
            </span>
          )}
        </div>
      ),
    },
    {
      id: "fleet",
      header: "Allocated Fleet",
      cell: (row) => {
        if (row.vehicle && row.driver) {
          return (
            <div className="flex flex-col text-xs">
              <span className="font-mono font-medium text-on-surface flex items-center gap-1">
                <Truck className="h-3.5 w-3.5 text-primary" />
                {row.vehicle.license_plate}
              </span>
              <span className="text-[11px] text-on-surface-muted flex items-center gap-1 mt-0.5">
                <UserCheck className="h-3 w-3 text-emerald-500" />
                {row.driver.first_name} {row.driver.last_name}
              </span>
            </div>
          );
        }
        if (row.status === "CONFIRMED") {
          return <span className="text-xs text-primary font-medium">Assignment active</span>;
        }
        if (row.status === "ACCEPTED") {
          return <span className="text-xs text-warning font-medium">Pending Resource Handover</span>;
        }
        return <span className="text-xs text-on-surface-subtle italic">Not designated</span>;
      },
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => (
        <div className="flex flex-col gap-1">
          <StatusBadge status={row.status} />
          {row.status === "REQUESTED" && (
            <span className="text-[10px] text-warning flex items-center gap-0.5 font-medium">
              <Clock className="h-3 w-3" />
              Expires {new Date(row.expires_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          )}
        </div>
      ),
    },
    {
      id: "actions",
      header: "Actions",
      cell: (row) => (
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate(`/bookings/${row.id}`)}
            className="h-8 px-2.5 text-xs text-on-surface hover:text-primary flex items-center gap-1"
          >
            <Eye className="h-3.5 w-3.5" />
            Review
          </Button>
          {(row.status === "REQUESTED" || row.status === "PENDING_ACCEPTANCE" || row.status === "ACCEPTED") && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleOpenCancel(row)}
              className="h-8 px-2 text-xs text-critical hover:bg-critical-container border-rose-200"
              title="Cancel Tender"
            >
              <XCircle className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12 animate-in fade-in duration-200">
      <PageHeader
        title="Transporter Bookings & Dispatch"
        subtitle="Manage tender requests, carrier confirmations, vehicle allocations, and dispatch handoffs."
        breadcrumbs={[
          { label: "Dashboard", href: "/overview" },
          { label: "Bookings", href: "/bookings" },
        ]}
      />

      {/* KPI Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard
          title="Total Tenders"
          value={totalBookings}
          icon={<CalendarDays className="h-5 w-5 text-primary" />}
          period="Total lifetime tenders"
          accentColor="blue"
        />
        <MetricCard
          title="Pending Response"
          value={requestedCount}
          icon={<Clock className="h-5 w-5 text-amber-500" />}
          period="Awaiting carrier confirmation"
          accentColor="amber"
        />
        <MetricCard
          title="Confirmed Dispatch"
          value={confirmedCount}
          icon={<CheckCircle2 className="h-5 w-5 text-success" />}
          period="Vehicle & driver committed"
          accentColor="emerald"
        />
        <MetricCard
          title="Expired / Rejected"
          value={expiredOrRejectedCount}
          icon={<AlertTriangle className="h-5 w-5 text-rose-500" />}
          period="Released back to pool"
          accentColor="rose"
        />
      </div>

      {/* Main Filter & Table Card */}
      <Card className="p-5 shadow-sm border border-outline-variant bg-surface-card space-y-5">
        {/* Status Tabs */}
        <div className="flex items-center gap-1 border-b border-outline-variant pb-3 overflow-x-auto">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => {
                setStatusFilter(tab.value);
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors shrink-0 ${
                statusFilter === tab.value
                  ? "bg-primary text-white shadow-sm"
                  : "text-on-surface-muted hover:text-on-surface hover:bg-surface-container-low"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="relative w-full sm:w-80">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-on-surface-subtle" />
            <Input
              placeholder="Search tender reference, carrier..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 h-9 text-xs"
            />
          </div>

          <div className="text-xs text-on-surface-muted font-medium">
            Showing {data?.items.length || 0} of {data?.total || 0} tenders
          </div>
        </div>

        {/* Bookings DataTable */}
        <DataTable<BookingResponse>
          columns={columns}
          data={data?.items || []}
          keyExtractor={(row) => row.id}
          isLoading={isLoading}
          emptyTitle="No bookings found"
          emptyDescription="No transporter bookings found for the selected criteria."
          pagination={{
            currentPage: page,
            totalPages: data?.pages || 1,
            onPageChange: (newPage) => setPage(newPage),
            pageSize,
            totalItems: data?.total || 0,
          }}
        />
      </Card>

      {/* Cancel Booking Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={cancelModalOpen}
        title="Cancel Transporter Booking Tender"
        description={`Are you sure you want to cancel tender ${selectedBookingToCancel?.booking_reference}? The shipment will be released back to the dispatch pool.`}
        confirmLabel="Cancel Tender"
        cancelLabel="Keep Tender"
        variant="destructive"
        isLoading={cancelMutation.isPending}
        onConfirm={handleConfirmCancel}
        onClose={() => {
          setCancelModalOpen(false);
          setSelectedBookingToCancel(null);
        }}
      >
        <div className="mt-3">
          <label className="block text-xs font-medium text-on-surface mb-1">
            Cancellation Reason <span className="text-rose-500">*</span>:
          </label>
          <textarea
            rows={3}
            value={cancellationReason}
            onChange={(e) => setCancellationReason(e.target.value)}
            placeholder="e.g., Cargo pickup delayed, transporter requested cancellation, or re-negotiating route..."
            className="w-full text-xs rounded-md border border-outline-strong p-2 focus:ring-1 focus:ring-burnt-orange focus:outline-none"
          />
        </div>
      </ConfirmationDialog>
    </div>
  );
};
