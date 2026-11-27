import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Truck,
  CheckCircle2,
  Clock,
  XCircle,
  DollarSign,
  ExternalLink,
  ChevronLeft,
  FileText,
  History,
  Building2,
  AlertCircle,
  Copy,
  Check,
} from "lucide-react";
import {
  bookingApi,
  BookingAcceptRequest,
  BookingRejectRequest,
  BookingAssignResourceRequest,
  BookingCancelRequest,
} from "@/api/bookings";
import { getTransporter } from "@/api/transporters";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/ConfirmationDialog";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { useToast } from "@/context/ToastContext";

export const BookingDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [copied, setCopied] = useState(false);

  // Modals state
  const [acceptModalOpen, setAcceptModalOpen] = useState(false);
  const [acceptRate, setAcceptRate] = useState<string>("");
  const [acceptNotes, setAcceptNotes] = useState<string>("");
  const [acceptVehicleId, setAcceptVehicleId] = useState<string>("");
  const [acceptDriverId, setAcceptDriverId] = useState<string>("");

  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectionReason, setRejectionReason] = useState<string>("");

  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [assignVehicleId, setAssignVehicleId] = useState<string>("");
  const [assignDriverId, setAssignDriverId] = useState<string>("");
  const [assignNotes, setAssignNotes] = useState<string>("");

  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [cancellationReason, setCancellationReason] = useState<string>("");

  // Query Booking Detail
  const {
    data: booking,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["booking", id],
    queryFn: () => (id ? bookingApi.getBooking(id) : Promise.reject("No id")),
    enabled: !!id,
  });

  // Query Carrier Fleet for resource assignment
  const { data: transporterDetail } = useQuery({
    queryKey: ["transporter_detail", booking?.transporter_id],
    queryFn: () => (booking?.transporter_id ? getTransporter(booking.transporter_id) : Promise.reject("No transporter id")),
    enabled: !!booking?.transporter_id,
  });

  // Copy ref
  const handleCopyRef = () => {
    if (!booking) return;
    navigator.clipboard.writeText(booking.booking_reference);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Mutations
  const acceptMutation = useMutation({
    mutationFn: (payload: BookingAcceptRequest) =>
      bookingApi.acceptBooking(id!, payload),
    onSuccess: (res) => {
      if (res.status === "CONFIRMED") {
        toast.success("Dispatch Confirmed", "Booking confirmed and dispatch assignment activated!");
      } else {
        toast.success("Tender Accepted", "Tender accepted. Please allocate vehicle and driver to confirm dispatch.");
      }
      setAcceptModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["booking", id] });
      queryClient.invalidateQueries({ queryKey: ["bookings"] });
    },
    onError: (err: any) => {
      toast.error("Acceptance Failed", err.response?.data?.detail || "Could not accept booking.");
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (payload: BookingRejectRequest) =>
      bookingApi.rejectBooking(id!, payload),
    onSuccess: () => {
      toast.info("Tender Rejected", "Booking tender rejected. Shipment released back to eligible matching pool.");
      setRejectModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["booking", id] });
      queryClient.invalidateQueries({ queryKey: ["bookings"] });
    },
    onError: (err: any) => {
      toast.error("Rejection Failed", err.response?.data?.detail || "Could not reject booking.");
    },
  });

  const assignMutation = useMutation({
    mutationFn: (payload: BookingAssignResourceRequest) =>
      bookingApi.assignResources(id!, payload),
    onSuccess: () => {
      toast.success("Fleet Allocated", "Vehicle and driver assigned. Booking confirmed and shipment marked COMMITTED.");
      setAssignModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["booking", id] });
      queryClient.invalidateQueries({ queryKey: ["bookings"] });
    },
    onError: (err: any) => {
      toast.error("Allocation Failed", err.response?.data?.detail || "Could not allocate fleet resources.");
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (payload: BookingCancelRequest) =>
      bookingApi.cancelBooking(id!, payload),
    onSuccess: () => {
      toast.info("Booking Cancelled", "Booking tender cancelled and shipment released.");
      setCancelModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["booking", id] });
      queryClient.invalidateQueries({ queryKey: ["bookings"] });
    },
    onError: (err: any) => {
      toast.error("Cancellation Failed", err.response?.data?.detail || "Could not cancel booking tender.");
    },
  });

  if (isLoading) {
    return <LoadingState text="Loading booking tender details..." />;
  }

  if (isError || !booking) {
    return (
      <ErrorState
        title="Booking Tender Not Found"
        message="The requested booking tender could not be found or you don't have permission to view it."
        onRetry={refetch}
      />
    );
  }

  // Pre-fill modals when opening
  const handleOpenAccept = () => {
    setAcceptRate(booking.offered_rate ? booking.offered_rate.toString() : "");
    setAcceptNotes("");
    setAcceptVehicleId("");
    setAcceptDriverId("");
    setAcceptModalOpen(true);
  };

  const handleOpenAssign = () => {
    setAssignVehicleId("");
    setAssignDriverId("");
    setAssignNotes("");
    setAssignModalOpen(true);
  };

  const handleConfirmAccept = (e: React.FormEvent) => {
    e.preventDefault();
    acceptMutation.mutate({
      agreed_rate: acceptRate ? parseFloat(acceptRate) : undefined,
      response_notes: acceptNotes.trim() || undefined,
      vehicle_id: acceptVehicleId || undefined,
      driver_id: acceptDriverId || undefined,
    });
  };

  const handleConfirmAssign = (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignVehicleId || !assignDriverId) {
      toast.error("Incomplete Selection", "Please designate both a vehicle and a driver.");
      return;
    }
    assignMutation.mutate({
      vehicle_id: assignVehicleId,
      driver_id: assignDriverId,
      notes: assignNotes.trim() || undefined,
    });
  };

  const handleConfirmReject = () => {
    if (!rejectionReason.trim()) {
      toast.error("Reason Required", "Please enter an operational justification for rejection.");
      return;
    }
    rejectMutation.mutate({
      rejection_reason: rejectionReason.trim(),
    });
  };

  const handleConfirmCancel = () => {
    if (!cancellationReason.trim()) {
      toast.error("Reason Required", "Please enter a cancellation reason.");
      return;
    }
    cancelMutation.mutate({
      cancellation_reason: cancellationReason.trim(),
    });
  };

  const isExpired = booking.is_expired;
  const canAcceptOrReject =
    (booking.status === "REQUESTED" || booking.status === "PENDING_ACCEPTANCE") && !isExpired;
  const canAssignResources = booking.status === "ACCEPTED";
  const canCancel =
    (booking.status === "REQUESTED" ||
      booking.status === "PENDING_ACCEPTANCE" ||
      booking.status === "ACCEPTED") &&
    !isExpired;

  const vehiclesList = transporterDetail?.vehicles || [];
  const driversList = transporterDetail?.drivers || [];

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16 animate-in fade-in duration-200">
      {/* Top Breadcrumb & Action Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-outline-variant pb-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-on-surface-muted mb-1">
            <Link to="/bookings" className="hover:text-primary flex items-center gap-0.5">
              <ChevronLeft className="h-3.5 w-3.5" />
              Bookings
            </Link>
            <span>/</span>
            <span className="font-mono text-on-surface font-medium">{booking.booking_reference}</span>
          </div>

          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-on-surface tracking-tight flex items-center gap-2">
              <span>{booking.booking_reference}</span>
              <button
                onClick={handleCopyRef}
                className="text-on-surface-subtle hover:text-on-surface-muted p-1 rounded hover:bg-surface-container"
                title="Copy Reference"
              >
                {copied ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}
              </button>
            </h1>
            <StatusBadge status={booking.status} />
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {canAcceptOrReject && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setRejectionReason("");
                  setRejectModalOpen(true);
                }}
                className="text-critical border-rose-200 hover:bg-critical-container text-xs"
              >
                <XCircle className="h-4 w-4 mr-1.5" />
                Reject Tender
              </Button>
              <Button
                size="sm"
                onClick={handleOpenAccept}
                className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs shadow-sm"
              >
                <CheckCircle2 className="h-4 w-4 mr-1.5" />
                Accept Tender
              </Button>
            </>
          )}

          {canAssignResources && (
            <Button
              size="sm"
              onClick={handleOpenAssign}
              className="bg-primary hover:bg-burnt-orange text-white text-xs shadow-sm"
            >
              <Truck className="h-4 w-4 mr-1.5" />
              Allocate Vehicle & Driver
            </Button>
          )}

          {canCancel && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setCancellationReason("");
                setCancelModalOpen(true);
              }}
              className="text-on-surface-muted hover:text-critical hover:bg-critical-container text-xs"
            >
              Cancel Tender
            </Button>
          )}

          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            className="text-on-surface-muted text-xs"
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Expiration or Rejection Warning Alert */}
      {isExpired && (
        <div className="p-4 rounded-xl bg-warning-container border border-amber-200 text-amber-800 flex items-start gap-3">
          <Clock className="h-5 w-5 text-warning shrink-0 mt-0.5" />
          <div className="text-xs">
            <span className="font-semibold block text-sm">Tender Expired</span>
            This booking tender expired on {new Date(booking.expires_at).toLocaleString()}. The associated shipment was released back to the matching pool.
          </div>
        </div>
      )}

      {booking.status === "REJECTED" && (
        <div className="p-4 rounded-xl bg-critical-container border border-rose-200 text-rose-800 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-critical shrink-0 mt-0.5" />
          <div className="text-xs">
            <span className="font-semibold block text-sm">Tender Rejected by Transporter</span>
            <p className="mt-0.5"><strong>Reason:</strong> {booking.rejection_reason || "No reason specified."}</p>
          </div>
        </div>
      )}

      {/* Main Grid: 2 cols left, 1 col right */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 cols) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Shipment & Lane Summary */}
          <Card className="p-5 border border-outline-variant bg-surface-card shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-outline-variant pb-3">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-bold text-on-surface">Shipment & Lane Specifications</h3>
              </div>
              {booking.shipment && (
                <Link
                  to={`/shipments/${booking.shipment_id}`}
                  className="text-xs font-semibold text-primary hover:underline flex items-center gap-1"
                >
                  View Shipment
                  <ExternalLink className="h-3 w-3" />
                </Link>
              )}
            </div>

            {booking.shipment ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between bg-surface-container-low p-3 rounded-lg border border-outline-variant">
                  <div>
                    <span className="text-[11px] text-on-surface-muted uppercase font-semibold">Tracking Number</span>
                    <p className="font-mono text-sm font-bold text-on-surface">{booking.shipment.tracking_number}</p>
                  </div>
                  <div className="text-right">
                    <span className="text-[11px] text-on-surface-muted uppercase font-semibold">Shipment Status</span>
                    <div className="mt-0.5">
                      <StatusBadge status={booking.shipment.status} />
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="p-3 rounded-lg border border-outline-variant bg-surface-card">
                    <span className="text-[11px] text-on-surface-subtle font-semibold uppercase">Origin / Pickup</span>
                    <p className="font-semibold text-on-surface mt-1">{booking.shipment.origin_name}</p>
                    <p className="text-on-surface-muted">{booking.shipment.origin_city}, {booking.shipment.origin_state}</p>
                    <div className="mt-2 text-[11px] text-on-surface-muted flex items-center gap-1">
                      <Clock className="h-3 w-3 text-on-surface-subtle" />
                      Pickup: {new Date(booking.shipment.scheduled_pickup_time).toLocaleString()}
                    </div>
                  </div>

                  <div className="p-3 rounded-lg border border-outline-variant bg-surface-card">
                    <span className="text-[11px] text-on-surface-subtle font-semibold uppercase">Destination / Delivery</span>
                    <p className="font-semibold text-on-surface mt-1">{booking.shipment.destination_name}</p>
                    <p className="text-on-surface-muted">{booking.shipment.destination_city}, {booking.shipment.destination_state}</p>
                    <div className="mt-2 text-[11px] text-on-surface-muted flex items-center gap-1">
                      <Clock className="h-3 w-3 text-on-surface-subtle" />
                      Delivery: {new Date(booking.shipment.expected_delivery_time).toLocaleString()}
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap gap-4 pt-1 text-xs">
                  <div className="flex-1 min-w-[140px] bg-surface-container-low p-2.5 rounded border border-outline-variant">
                    <span className="text-on-surface-subtle text-[10px] uppercase font-semibold">Payload Weight</span>
                    <p className="text-sm font-bold text-on-surface mt-0.5">
                      {booking.shipment.total_weight_kg.toLocaleString()} kg
                    </p>
                  </div>
                  <div className="flex-1 min-w-[140px] bg-surface-container-low p-2.5 rounded border border-outline-variant">
                    <span className="text-on-surface-subtle text-[10px] uppercase font-semibold">Vehicle Requirement</span>
                    <p className="text-sm font-bold text-on-surface mt-0.5">
                      {booking.shipment.required_vehicle_type}
                    </p>
                  </div>
                  {booking.shipment.customer_name && (
                    <div className="flex-1 min-w-[140px] bg-surface-container-low p-2.5 rounded border border-outline-variant">
                      <span className="text-on-surface-subtle text-[10px] uppercase font-semibold">Client / Account</span>
                      <p className="text-sm font-bold text-on-surface mt-0.5">
                        {booking.shipment.customer_name}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-xs text-on-surface-subtle italic">Associated shipment information not available.</p>
            )}
          </Card>

          {/* Carrier Profile & Compliance */}
          <Card className="p-5 border border-outline-variant bg-surface-card shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-outline-variant pb-3">
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-success" />
                <h3 className="text-sm font-bold text-on-surface">Contracted Carrier</h3>
              </div>
              {booking.transporter && (
                <Link
                  to={`/transporters/${booking.transporter_id}`}
                  className="text-xs font-semibold text-primary hover:underline flex items-center gap-1"
                >
                  Carrier Dossier
                  <ExternalLink className="h-3 w-3" />
                </Link>
              )}
            </div>

            {booking.transporter ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div>
                  <h4 className="text-sm font-bold text-on-surface">{booking.transporter.name}</h4>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="px-2 py-0.5 rounded bg-surface-container text-on-surface font-mono font-medium text-[11px]">
                      {booking.transporter.code}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-success-container text-on-success-container font-semibold text-[11px]">
                      {booking.transporter.verification_status}
                    </span>
                  </div>
                  <div className="mt-3 text-on-surface-muted space-y-1">
                    <p>Phone: <strong>{booking.transporter.phone}</strong></p>
                    {booking.transporter.email && <p>Email: <strong>{booking.transporter.email}</strong></p>}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-success-container/50 border border-emerald-100 flex flex-col justify-between">
                  <span className="text-[11px] text-emerald-800 font-semibold uppercase">
                    Historical Reliability Score
                  </span>
                  <div className="my-2 flex items-baseline gap-2">
                    <span className="text-3xl font-black text-on-success-container">
                      {booking.transporter.reliability_score.toFixed(0)}%
                    </span>
                    <span className="text-xs text-success font-medium">On-time pickup compliance</span>
                  </div>
                  <div className="w-full bg-emerald-200/50 h-2 rounded-full overflow-hidden">
                    <div
                      className="bg-emerald-600 h-full rounded-full transition-all"
                      style={{ width: `${booking.transporter.reliability_score}%` }}
                    />
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-on-surface-subtle italic">No carrier profile attached.</p>
            )}
          </Card>

          {/* Allocated Fleet & Crew Details */}
          <Card className="p-5 border border-outline-variant bg-surface-card shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-outline-variant pb-3">
              <div className="flex items-center gap-2">
                <Truck className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-bold text-on-surface">Allocated Fleet Unit & Crew</h3>
              </div>
              {canAssignResources && (
                <Button
                  size="sm"
                  onClick={handleOpenAssign}
                  className="h-7 text-xs bg-primary hover:bg-burnt-orange text-white"
                >
                  Allocate Resources
                </Button>
              )}
            </div>

            {booking.vehicle && booking.driver ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Vehicle */}
                <div className="p-4 rounded-xl border border-outline-variant bg-surface-container-low/60 text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-on-surface-subtle uppercase tracking-wider">
                      Vehicle Unit
                    </span>
                    <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold">
                      ACTIVE
                    </span>
                  </div>
                  <div className="text-base font-black font-mono text-on-surface">
                    {booking.vehicle.license_plate}
                  </div>
                  <div className="text-on-surface-muted">
                    Type: <strong>{booking.vehicle.vehicle_type}</strong>
                  </div>
                  <div className="text-on-surface-muted">
                    Capacity: <strong>{booking.vehicle.capacity_kg.toLocaleString()} kg</strong>
                  </div>
                  {booking.vehicle.insurance_expiry && (
                    <div className="text-[11px] text-on-surface-muted">
                      Insurance: Valid through {new Date(booking.vehicle.insurance_expiry).toLocaleDateString()}
                    </div>
                  )}
                </div>

                {/* Driver */}
                <div className="p-4 rounded-xl border border-outline-variant bg-surface-container-low/60 text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-on-surface-subtle uppercase tracking-wider">
                      Driver Operator
                    </span>
                    <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold">
                      {booking.driver.account_status}
                    </span>
                  </div>
                  <div className="text-base font-bold text-on-surface">
                    {booking.driver.first_name} {booking.driver.last_name}
                  </div>
                  <div className="text-on-surface-muted">
                    Phone: <strong>{booking.driver.phone}</strong>
                  </div>
                  <div className="text-on-surface-muted font-mono">
                    License: <strong>{booking.driver.license_number}</strong>
                  </div>
                  {booking.driver.license_expiry && (
                    <div className="text-[11px] text-on-surface-muted">
                      License Expiry: {new Date(booking.driver.license_expiry).toLocaleDateString()}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-6 rounded-xl border border-dashed border-outline-variant bg-surface-container-low text-center space-y-2">
                <Truck className="h-8 w-8 text-on-surface-muted mx-auto" />
                <h4 className="text-xs font-semibold text-on-surface">No Fleet Unit Designated Yet</h4>
                <p className="text-[11px] text-on-surface-muted max-w-sm mx-auto">
                  {booking.status === "ACCEPTED"
                    ? "Carrier has accepted the tender terms. Allocate a compliant vehicle and driver to confirm dispatch."
                    : "Vehicle and driver units will be assigned upon tender acceptance."}
                </p>
                {canAssignResources && (
                  <Button
                    size="sm"
                    onClick={handleOpenAssign}
                    className="mt-2 text-xs bg-primary hover:bg-burnt-orange text-white"
                  >
                    Allocate Fleet Now
                  </Button>
                )}
              </div>
            )}
          </Card>

          {/* Append-only Milestone Event Stream */}
          <Card className="p-5 border border-outline-variant bg-surface-card shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-outline-variant pb-3">
              <div className="flex items-center gap-2">
                <History className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-bold text-on-surface">Tender Milestone Events</h3>
              </div>
              <span className="text-[11px] text-on-surface-subtle font-medium">Immutable Audit Trail</span>
            </div>

            {booking.events && booking.events.length > 0 ? (
              <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-surface-container">
                {booking.events.map((ev, idx) => (
                  <div key={ev.id || idx} className="relative group">
                    <div className="absolute -left-6 top-1 h-2.5 w-2.5 rounded-full bg-primary ring-4 ring-white" />
                    <div className="text-xs font-semibold text-on-surface">{ev.description}</div>
                    <div className="flex items-center gap-2 mt-0.5 text-[10px] text-on-surface-subtle">
                      <span>{new Date(ev.occurred_at).toLocaleString()}</span>
                      <span>·</span>
                      <span className="font-mono">{ev.event_type}</span>
                      <span>·</span>
                      <span>Source: {ev.source}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-on-surface-subtle italic">No milestone events logged yet.</p>
            )}
          </Card>
        </div>

        {/* Right Column: Commercial & Operational Summary */}
        <div className="space-y-6">
          {/* Rate & Commercial Terms Card */}
          <Card className="p-5 border border-outline-variant bg-surface-card shadow-sm space-y-4">
            <div className="flex items-center gap-2 border-b border-outline-variant pb-3">
              <DollarSign className="h-4 w-4 text-success" />
              <h3 className="text-sm font-bold text-on-surface">Commercial Terms</h3>
            </div>

            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-on-surface-muted">Agreed Rate</span>
                <span className="font-bold text-base text-on-surface">
                  {booking.agreed_rate !== null && booking.agreed_rate !== undefined
                    ? `$${booking.agreed_rate.toLocaleString(undefined, { minimumFractionDigits: 2 })}`
                    : "Not finalized"}
                </span>
              </div>

              <div className="flex items-center justify-between border-t border-outline-variant pt-2">
                <span className="text-on-surface-muted">Initial Offered Rate</span>
                <span className="font-medium text-on-surface">
                  {booking.offered_rate !== null && booking.offered_rate !== undefined
                    ? `$${booking.offered_rate.toLocaleString(undefined, { minimumFractionDigits: 2 })}`
                    : "Tariff quote"}
                </span>
              </div>

              <div className="flex items-center justify-between border-t border-outline-variant pt-2">
                <span className="text-on-surface-muted">Tender Deadline</span>
                <span className="font-medium text-on-surface">
                  {new Date(booking.expires_at).toLocaleString()}
                </span>
              </div>

              {booking.responded_at && (
                <div className="flex items-center justify-between border-t border-outline-variant pt-2">
                  <span className="text-on-surface-muted">Responded At</span>
                  <span className="font-medium text-on-surface">
                    {new Date(booking.responded_at).toLocaleString()}
                  </span>
                </div>
              )}

              {booking.confirmed_at && (
                <div className="flex items-center justify-between border-t border-outline-variant pt-2 text-on-success-container font-medium">
                  <span className="flex items-center gap-1">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Confirmed Dispatch
                  </span>
                  <span>{new Date(booking.confirmed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                </div>
              )}

              {booking.assignment_id && (
                <div className="flex items-center justify-between border-t border-outline-variant pt-2">
                  <span className="text-on-surface-muted">Active Assignment</span>
                  <span className="font-mono text-[11px] text-primary font-semibold truncate max-w-[140px]" title={booking.assignment_id}>
                    {booking.assignment_id.slice(0, 8)}...
                  </span>
                </div>
              )}
            </div>
          </Card>

          {/* Response Notes / Operational Instructions */}
          {(booking.response_notes || booking.rejection_reason) && (
            <Card className="p-5 border border-outline-variant bg-surface-card shadow-sm space-y-3">
              <h3 className="text-sm font-bold text-on-surface">Operational Notes</h3>
              {booking.response_notes && (
                <div className="text-xs bg-surface-container-low p-3 rounded-lg border border-outline-variant text-on-surface">
                  <span className="font-semibold block text-[11px] text-on-surface-subtle uppercase mb-1">
                    Carrier Acceptance Notes
                  </span>
                  {booking.response_notes}
                </div>
              )}
              {booking.rejection_reason && (
                <div className="text-xs bg-critical-container p-3 rounded-lg border border-rose-100 text-rose-800">
                  <span className="font-semibold block text-[11px] text-rose-500 uppercase mb-1">
                    Rejection Justification
                  </span>
                  {booking.rejection_reason}
                </div>
              )}
            </Card>
          )}

          {/* Quick Action Box for Pending Tenders */}
          {canAcceptOrReject && (
            <Card className="p-5 border border-burnt-orange/30 bg-primary-container/50 shadow-sm space-y-3">
              <h3 className="text-sm font-bold text-on-surface">Carrier Action Required</h3>
              <p className="text-xs text-on-surface-muted">
                This tender is awaiting carrier response. You may review and accept terms, or reject if equipment is unavailable.
              </p>
              <div className="flex flex-col gap-2 pt-2">
                <Button
                  onClick={handleOpenAccept}
                  className="w-full bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold"
                >
                  <CheckCircle2 className="h-4 w-4 mr-1.5" />
                  Accept Tender Terms
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    setRejectionReason("");
                    setRejectModalOpen(true);
                  }}
                  className="w-full text-critical border-rose-200 hover:bg-critical-container text-xs"
                >
                  <XCircle className="h-4 w-4 mr-1.5" />
                  Reject Tender
                </Button>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* MODAL 1: ACCEPT TENDER */}
      {acceptModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-card/50 backdrop-blur-sm p-4">
          <div className="bg-surface-card rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-outline-variant pb-3">
              <h3 className="text-base font-bold text-on-surface flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-success" />
                Accept Booking Tender
              </h3>
              <button
                onClick={() => setAcceptModalOpen(false)}
                className="text-on-surface-subtle hover:text-on-surface-muted text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleConfirmAccept} className="space-y-4">
              <p className="text-xs text-on-surface-muted">
                Confirm rate terms and optionally designate fleet equipment to confirm dispatch immediately.
              </p>

              <div>
                <label className="block text-xs font-semibold text-on-surface mb-1">
                  Agreed Rate ($):
                </label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={acceptRate}
                  onChange={(e) => setAcceptRate(e.target.value)}
                  placeholder="e.g. 1850.00"
                  className="text-xs"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-on-surface mb-1">
                  Designate Vehicle Unit (Optional):
                </label>
                <select
                  value={acceptVehicleId}
                  onChange={(e) => setAcceptVehicleId(e.target.value)}
                  className="w-full text-xs rounded-md border border-outline-strong p-2 focus:ring-1 focus:ring-burnt-orange focus:outline-none"
                >
                  <option value="">-- Assign Later --</option>
                  {vehiclesList.map((v) => (
                    <option key={v.id} value={v.id} disabled={!v.is_available}>
                      {v.license_plate} - {v.vehicle_type} ({v.capacity_kg}kg) {!v.is_available ? "(Unavailable)" : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-on-surface mb-1">
                  Designate Driver Operator (Optional):
                </label>
                <select
                  value={acceptDriverId}
                  onChange={(e) => setAcceptDriverId(e.target.value)}
                  className="w-full text-xs rounded-md border border-outline-strong p-2 focus:ring-1 focus:ring-burnt-orange focus:outline-none"
                >
                  <option value="">-- Assign Later --</option>
                  {driversList.map((d) => (
                    <option key={d.id} value={d.id} disabled={!d.is_available}>
                      {d.first_name} {d.last_name} ({d.phone}) {!d.is_available ? "(Unavailable)" : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-on-surface mb-1">
                  Acceptance Notes / Handover Details:
                </label>
                <textarea
                  rows={2}
                  value={acceptNotes}
                  onChange={(e) => setAcceptNotes(e.target.value)}
                  placeholder="e.g., Driver confirmed for 08:00 AM pickup. Equipment inspected."
                  className="w-full text-xs rounded-md border border-outline-strong p-2 focus:ring-1 focus:ring-burnt-orange focus:outline-none"
                />
              </div>

              {acceptVehicleId && acceptDriverId && (
                <div className="p-3 rounded-lg bg-success-container border border-emerald-200 text-emerald-800 text-xs">
                  <strong>Instant Confirmation:</strong> Designating both vehicle and driver will immediately activate dispatch and transition shipment to COMMITTED.
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-outline-variant">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setAcceptModalOpen(false)}
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={acceptMutation.isPending}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold"
                >
                  {acceptMutation.isPending ? "Confirming..." : "Confirm Acceptance"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: ASSIGN RESOURCES */}
      {assignModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-card/50 backdrop-blur-sm p-4">
          <div className="bg-surface-card rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-outline-variant pb-3">
              <h3 className="text-base font-bold text-on-surface flex items-center gap-2">
                <Truck className="h-5 w-5 text-primary" />
                Allocate Fleet & Driver
              </h3>
              <button
                onClick={() => setAssignModalOpen(false)}
                className="text-on-surface-subtle hover:text-on-surface-muted text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleConfirmAssign} className="space-y-4">
              <p className="text-xs text-on-surface-muted">
                Select an eligible vehicle meeting cargo capacity ({booking.shipment?.total_weight_kg.toLocaleString()}kg) and an unexpired licensed driver.
              </p>

              <div>
                <label className="block text-xs font-semibold text-on-surface mb-1">
                  Select Vehicle Unit <span className="text-rose-500">*</span>:
                </label>
                <select
                  required
                  value={assignVehicleId}
                  onChange={(e) => setAssignVehicleId(e.target.value)}
                  className="w-full text-xs rounded-md border border-outline-strong p-2 focus:ring-1 focus:ring-burnt-orange focus:outline-none"
                >
                  <option value="">-- Choose Eligible Vehicle --</option>
                  {vehiclesList.map((v) => {
                    const cargoWeight = booking.shipment?.total_weight_kg || 0;
                    const insufficientCapacity = v.capacity_kg < cargoWeight;
                    return (
                      <option
                        key={v.id}
                        value={v.id}
                        disabled={!v.is_available || insufficientCapacity}
                      >
                        {v.license_plate} - {v.vehicle_type} ({v.capacity_kg}kg)
                        {insufficientCapacity ? " [Capacity Insufficient]" : ""}
                        {!v.is_available ? " [Unavailable]" : ""}
                      </option>
                    );
                  })}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-on-surface mb-1">
                  Select Driver Operator <span className="text-rose-500">*</span>:
                </label>
                <select
                  required
                  value={assignDriverId}
                  onChange={(e) => setAssignDriverId(e.target.value)}
                  className="w-full text-xs rounded-md border border-outline-strong p-2 focus:ring-1 focus:ring-burnt-orange focus:outline-none"
                >
                  <option value="">-- Choose Available Driver --</option>
                  {driversList.map((d) => (
                    <option key={d.id} value={d.id} disabled={!d.is_available || d.is_license_expired}>
                      {d.first_name} {d.last_name} ({d.phone}) {d.is_license_expired ? "[License Expired]" : ""} {!d.is_available ? "[Unavailable]" : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-on-surface mb-1">
                  Dispatch Handover Notes:
                </label>
                <textarea
                  rows={2}
                  value={assignNotes}
                  onChange={(e) => setAssignNotes(e.target.value)}
                  placeholder="e.g. Gate pass arranged. Safety gear issued."
                  className="w-full text-xs rounded-md border border-outline-strong p-2 focus:ring-1 focus:ring-burnt-orange focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-outline-variant">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setAssignModalOpen(false)}
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={assignMutation.isPending}
                  className="bg-primary hover:bg-burnt-orange text-white text-xs font-semibold"
                >
                  {assignMutation.isPending ? "Allocating..." : "Confirm Fleet Allocation"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 3: REJECT TENDER */}
      <ConfirmationDialog
        isOpen={rejectModalOpen}
        title="Reject Tender Request"
        description="Are you sure you want to reject this booking tender? The shipment will be released back to the dispatch matching pool."
        confirmLabel="Confirm Rejection"
        cancelLabel="Keep Tender"
        variant="destructive"
        isLoading={rejectMutation.isPending}
        onConfirm={handleConfirmReject}
        onClose={() => setRejectModalOpen(false)}
      >
        <div className="mt-3">
          <label className="block text-xs font-semibold text-on-surface mb-1">
            Operational Rejection Reason <span className="text-rose-500">*</span>:
          </label>
          <textarea
            rows={3}
            value={rejectionReason}
            onChange={(e) => setRejectionReason(e.target.value)}
            placeholder="e.g., Fleet capacity fully booked, rate unacceptable, route restricted..."
            className="w-full text-xs rounded-md border border-outline-strong p-2 focus:ring-1 focus:ring-burnt-orange focus:outline-none"
          />
        </div>
      </ConfirmationDialog>

      {/* MODAL 4: CANCEL TENDER */}
      <ConfirmationDialog
        isOpen={cancelModalOpen}
        title="Cancel Transporter Booking Tender"
        description={`Are you sure you want to cancel tender ${booking.booking_reference}? Any active vehicle allocations will be released.`}
        confirmLabel="Cancel Tender"
        cancelLabel="Keep Tender"
        variant="destructive"
        isLoading={cancelMutation.isPending}
        onConfirm={handleConfirmCancel}
        onClose={() => setCancelModalOpen(false)}
      >
        <div className="mt-3">
          <label className="block text-xs font-semibold text-on-surface mb-1">
            Cancellation Reason <span className="text-rose-500">*</span>:
          </label>
          <textarea
            rows={3}
            value={cancellationReason}
            onChange={(e) => setCancellationReason(e.target.value)}
            placeholder="e.g., Customer rescheduled cargo readiness, route re-tendered..."
            className="w-full text-xs rounded-md border border-outline-strong p-2 focus:ring-1 focus:ring-burnt-orange focus:outline-none"
          />
        </div>
      </ConfirmationDialog>
    </div>
  );
};
