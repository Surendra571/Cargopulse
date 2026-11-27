import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  FileText,
  MapPin,
  Clock,
  Truck,
  ArrowLeft,
  Printer,
  History,
  Camera,
  ExternalLink,
  Loader2,
  X,
} from "lucide-react";
import { getShipmentPOD, reviewPOD, ProofOfDelivery } from "@/api/pod";

export const PODReviewPage: React.FC = () => {
  const { shipmentId } = useParams<{ shipmentId: string }>();
  const navigate = useNavigate();

  const [pod, setPod] = useState<ProofOfDelivery | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Review modal states
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectionReason, setRejectionReason] = useState("");
  const [reviewNotes, setReviewNotes] = useState("");
  const [selectedPhoto, setSelectedPhoto] = useState<string | null>(null);

  const fetchPOD = async () => {
    if (!shipmentId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getShipmentPOD(shipmentId);
      setPod(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Proof of delivery has not yet been submitted or could not be loaded.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPOD();
  }, [shipmentId]);

  const handleReviewAction = async (action: "APPROVE" | "REJECT" | "FLAG_DISCREPANCY") => {
    if (!shipmentId) return;
    setActionLoading(true);
    try {
      const updated = await reviewPOD(shipmentId, {
        action,
        rejection_reason: action === "REJECT" ? rejectionReason : undefined,
        notes: reviewNotes || undefined,
      });
      setPod(updated);
      setRejectModalOpen(false);
      setRejectionReason("");
      setReviewNotes("");
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to update POD review status.");
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-surface-container-low flex items-center justify-center p-6">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <p className="text-sm font-medium text-on-surface-muted">Retrieving digital proof of delivery...</p>
        </div>
      </div>
    );
  }

  if (error || !pod) {
    return (
      <div className="min-h-screen bg-surface-container-low p-6 flex items-center justify-center">
        <div className="max-w-md w-full bg-surface-card rounded-2xl shadow-sm border border-outline-variant p-6 text-center">
          <div className="w-12 h-12 rounded-full bg-amber-100 text-warning flex items-center justify-center mx-auto mb-3">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <h2 className="text-lg font-bold text-on-surface mb-1">POD Evidence Pending</h2>
          <p className="text-sm text-on-surface-muted mb-6">{error || "No proof of delivery record exists for this shipment."}</p>
          <div className="space-y-2">
            <Link
              to={`/pod/submit/${shipmentId}`}
              className="w-full inline-flex justify-center items-center gap-2 px-4 py-2 rounded-lg bg-primary text-white font-medium text-sm hover:bg-burnt-orange"
            >
              Submit Driver POD Now
            </Link>
            <button
              onClick={() => navigate(-1)}
              className="w-full inline-flex justify-center items-center gap-2 px-4 py-2 rounded-lg border border-outline-strong text-on-surface font-medium text-sm hover:bg-surface-container-low"
            >
              Go Back
            </button>
          </div>
        </div>
      </div>
    );
  }

  const isVerified = pod.verification_status === "VERIFIED";
  const isFlagged = pod.verification_status === "DISCREPANCY_FLAGGED";
  const isRejected = pod.verification_status === "REJECTED";

  return (
    <div className="min-h-screen bg-surface-container-low pb-16">
      {/* Top Header */}
      <div className="bg-surface-card border-b border-outline-variant sticky top-0 z-20 px-4 sm:px-8 py-3 shadow-sm">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(-1)}
              className="p-1.5 rounded-lg border border-outline-variant hover:bg-surface-container-low text-on-surface-muted"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-on-surface-subtle font-medium">Proof of Delivery Review</span>
                <span className="text-xs font-mono font-bold text-primary bg-primary-container px-2 py-0.5 rounded">
                  {pod.tracking_number}
                </span>
              </div>
              <h1 className="text-lg font-bold text-on-surface">
                Delivery Evidence & Verification
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => window.print()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-outline-strong text-on-surface text-xs font-medium hover:bg-surface-container-low shadow-sm"
            >
              <Printer className="w-3.5 h-3.5" /> Print ePOD
            </button>
            <Link
              to={`/tracking/${shipmentId}`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container text-on-surface text-xs font-medium hover:bg-surface-container"
            >
              Live Tracking
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-8 pt-6 space-y-6">
        {/* Status & Discrepancy Banner */}
        <div className={`rounded-xl border p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
          isVerified
            ? "bg-success-container/70 border-emerald-200 text-emerald-900"
            : isFlagged
            ? "bg-warning-container border-amber-200 text-amber-900"
            : isRejected
            ? "bg-red-50 border-red-200 text-red-900"
            : "bg-primary-container/70 border-burnt-orange/30 text-blue-900"
        }`}>
          <div className="flex items-start gap-3.5">
            <div className={`p-2 rounded-lg ${
              isVerified ? "bg-emerald-100 text-on-success-container" :
              isFlagged ? "bg-amber-100 text-on-warning-container" :
              isRejected ? "bg-red-100 text-red-700" :
              "bg-primary-container text-primary"
            }`}>
              {isVerified && <CheckCircle2 className="w-6 h-6" />}
              {isFlagged && <AlertTriangle className="w-6 h-6" />}
              {isRejected && <XCircle className="w-6 h-6" />}
              {!isVerified && !isFlagged && !isRejected && <Clock className="w-6 h-6" />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-base">
                  {isVerified && "Verified & Approved Delivery"}
                  {isFlagged && "Delivery Discrepancies Flagged"}
                  {isRejected && "Proof of Delivery Rejected"}
                  {!isVerified && !isFlagged && !isRejected && "Pending Manufacturer Verification"}
                </span>
                <span className="text-xs px-2 py-0.5 rounded font-mono font-bold uppercase bg-surface-card/70 border">
                  {pod.verification_status}
                </span>
              </div>
              <p className="text-xs opacity-85 mt-0.5">
                Delivered on {new Date(pod.signed_at).toLocaleString()} • Signed by: <span className="font-semibold">{pod.signed_by_name}</span>
                {pod.recipient_phone && ` (${pod.recipient_phone})`}
              </p>
            </div>
          </div>

          {/* Quick Review Actions */}
          <div className="flex items-center gap-2">
            {!isVerified && (
              <button
                disabled={actionLoading}
                onClick={() => handleReviewAction("APPROVE")}
                className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-sm transition inline-flex items-center gap-1"
              >
                <CheckCircle2 className="w-3.5 h-3.5" /> Approve POD
              </button>
            )}
            {!isFlagged && (
              <button
                disabled={actionLoading}
                onClick={() => handleReviewAction("FLAG_DISCREPANCY")}
                className="px-3 py-1.5 rounded-lg border border-amber-300 bg-surface-card hover:bg-warning-container text-amber-800 text-xs font-bold transition inline-flex items-center gap-1"
              >
                <AlertTriangle className="w-3.5 h-3.5" /> Flag Discrepancy
              </button>
            )}
            {!isRejected && (
              <button
                disabled={actionLoading}
                onClick={() => setRejectModalOpen(true)}
                className="px-3 py-1.5 rounded-lg border border-red-300 bg-surface-card hover:bg-red-50 text-red-700 text-xs font-bold transition inline-flex items-center gap-1"
              >
                <XCircle className="w-3.5 h-3.5" /> Reject
              </button>
            )}
          </div>
        </div>

        {/* Detailed Discrepancy Alert Box */}
        {(pod.is_shortage || pod.is_damaged || pod.rejection_reason) && (
          <div className="bg-surface-card rounded-xl shadow-sm border border-red-200 overflow-hidden">
            <div className="bg-red-50/80 px-4 py-2.5 border-b border-red-100 flex items-center justify-between">
              <span className="text-xs font-bold text-red-900 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-red-600" /> Discrepancies & Audit Exceptions
              </span>
              <span className="text-[11px] font-semibold text-red-700">Commercial Investigation Required</span>
            </div>
            <div className="p-4 space-y-3 text-xs">
              {pod.is_shortage && (
                <div className="p-3 bg-red-50/50 rounded-lg border border-red-100 flex items-start gap-3">
                  <div className="font-bold text-red-700">SHORTAGE:</div>
                  <div>
                    <span className="font-bold text-red-900">Missing {pod.shortage_quantity} of {pod.expected_quantity} packages</span>
                    <p className="text-on-surface-muted mt-0.5">{pod.shortage_description || "Shortage noted during recipient count."}</p>
                  </div>
                </div>
              )}
              {pod.is_damaged && (
                <div className="p-3 bg-warning-container/50 rounded-lg border border-amber-100 flex items-start gap-3">
                  <div className="font-bold text-on-warning-container">DAMAGE:</div>
                  <div>
                    <span className="font-bold text-amber-900">{pod.damage_severity} Cargo Damage</span>
                    <p className="text-on-surface-muted mt-0.5">{pod.damage_description || "Physical damage reported at dock."}</p>
                  </div>
                </div>
              )}
              {pod.rejection_reason && (
                <div className="p-3 bg-surface-container-low rounded-lg border border-outline-variant flex items-start gap-3">
                  <div className="font-bold text-on-surface">REJECTION REASON:</div>
                  <div className="text-on-surface">{pod.rejection_reason}</div>
                </div>
              )}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* LEFT 2 COLS: Evidence Gallery & Recipient Signoff */}
          <div className="lg:col-span-2 space-y-6">
            {/* Photographic Delivery Proof */}
            <div className="bg-surface-card rounded-xl shadow-sm border border-outline-variant p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-on-surface flex items-center gap-2">
                  <Camera className="w-4 h-4 text-primary" /> Delivery Photographs ({pod.delivery_photo_urls.length})
                </h2>
                <span className="text-xs text-on-surface-subtle">Verifiable dock evidence</span>
              </div>

              {pod.delivery_photo_urls.length > 0 ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {pod.delivery_photo_urls.map((url, idx) => (
                    <div
                      key={idx}
                      onClick={() => setSelectedPhoto(url)}
                      className="group relative rounded-xl overflow-hidden border border-outline-variant cursor-pointer bg-surface-container aspect-video"
                    >
                      <img src={url} alt={`Evidence ${idx + 1}`} className="w-full h-full object-cover group-hover:scale-105 transition" />
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white transition">
                        <ExternalLink className="w-5 h-5" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-8 text-center text-on-surface-subtle text-xs border border-dashed rounded-xl">
                  No photographic delivery evidence attached.
                </div>
              )}

              {/* Damage Photos (if present) */}
              {pod.damage_photo_urls && pod.damage_photo_urls.length > 0 && (
                <div className="pt-4 border-t border-outline-variant">
                  <h3 className="text-xs font-bold text-red-600 mb-2 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5" /> Damage Proof Photos ({pod.damage_photo_urls.length})
                  </h3>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {pod.damage_photo_urls.map((url, idx) => (
                      <div
                        key={idx}
                        onClick={() => setSelectedPhoto(url)}
                        className="group relative rounded-xl overflow-hidden border border-red-200 cursor-pointer bg-surface-container aspect-video"
                      >
                        <img src={url} alt={`Damage ${idx + 1}`} className="w-full h-full object-cover group-hover:scale-105 transition" />
                        <div className="absolute inset-0 bg-red-950/40 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white transition">
                          <ExternalLink className="w-5 h-5" />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Recipient Digital Signoff & Acknowledgement */}
            <div className="bg-surface-card rounded-xl shadow-sm border border-outline-variant p-5 space-y-4">
              <h2 className="text-sm font-bold text-on-surface flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-success" /> Recipient Signoff & Acknowledgement
              </h2>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Signature Box */}
                <div className="border border-outline-variant rounded-xl p-3 bg-surface-container-low flex flex-col items-center justify-center text-center">
                  <span className="text-[11px] font-semibold text-on-surface-subtle mb-2 block">Captured Signature</span>
                  {pod.signature_image_url ? (
                    <img
                      src={pod.signature_image_url}
                      alt="Recipient Signature"
                      className="max-h-24 object-contain filter drop-shadow-sm"
                    />
                  ) : (
                    <span className="text-xs text-on-surface-subtle py-6 italic">No signature image data</span>
                  )}
                  <span className="text-[10px] text-on-surface-subtle mt-2">
                    Method: {pod.acknowledgement_type}
                  </span>
                </div>

                {/* Recipient Details */}
                <div className="space-y-2 text-xs">
                  <div className="p-2.5 bg-surface-container-low rounded-lg">
                    <span className="text-on-surface-subtle block text-[11px]">Authorized Signee</span>
                    <span className="font-bold text-on-surface text-sm">{pod.signed_by_name}</span>
                    {pod.signed_by_designation && (
                      <span className="text-on-surface-muted block">{pod.signed_by_designation}</span>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-2 bg-surface-container-low rounded-lg">
                      <span className="text-on-surface-subtle block text-[10px]">Phone</span>
                      <span className="font-semibold text-on-surface">{pod.recipient_phone || "Not provided"}</span>
                    </div>
                    <div className="p-2 bg-surface-container-low rounded-lg">
                      <span className="text-on-surface-subtle block text-[10px]">Email</span>
                      <span className="font-semibold text-on-surface truncate block">{pod.recipient_email || "Not provided"}</span>
                    </div>
                  </div>
                  <div className="p-2 bg-surface-container-low rounded-lg flex items-center justify-between">
                    <span className="text-on-surface-subtle text-[11px]">Signoff Timestamp</span>
                    <span className="font-mono text-on-surface font-semibold">{new Date(pod.signed_at).toLocaleString()}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Immutable Submission & Revision History */}
            <div className="bg-surface-card rounded-xl shadow-sm border border-outline-variant p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-on-surface flex items-center gap-2">
                  <History className="w-4 h-4 text-purple-600" /> Immutable Submission Audit Trail
                </h2>
                <span className="text-xs text-on-surface-subtle">
                  {pod.is_modified ? "Revisions Recorded" : "Original Submission"}
                </span>
              </div>

              <div className="relative pl-6 space-y-4 border-l-2 border-outline-variant">
                {pod.submission_history.map((rev, idx) => (
                  <div key={idx} className="relative text-xs">
                    <div className="absolute -left-[31px] top-0.5 w-3.5 h-3.5 rounded-full bg-primary border-2 border-white" />
                    <div className="flex items-center justify-between font-semibold text-on-surface">
                      <span>Revision #{rev.revision}: {rev.action}</span>
                      <span className="font-mono text-[11px] text-on-surface-subtle">
                        {new Date(rev.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <p className="text-on-surface-muted mt-0.5">
                      Actor: <span className="font-medium text-on-surface">{rev.submitted_by_email || rev.reviewed_by_email || "System"}</span>
                    </p>
                    {rev.notes && <p className="text-on-surface-muted bg-surface-container-low p-2 rounded mt-1">"{rev.notes}"</p>}
                    {rev.rejection_reason && (
                      <p className="text-red-600 bg-red-50 p-2 rounded mt-1 font-medium">Rejection Reason: {rev.rejection_reason}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* RIGHT COL: Geolocation, Driver Asset, & Verification Metadata */}
          <div className="space-y-6">
            {/* Delivery Location & Geofence Verification */}
            <div className="bg-surface-card rounded-xl shadow-sm border border-outline-variant p-5 space-y-4">
              <h2 className="text-sm font-bold text-on-surface flex items-center gap-2">
                <MapPin className="w-4 h-4 text-primary" /> Geolocation & Geofence
              </h2>

              <div className="space-y-3 text-xs">
                <div className="flex justify-between items-center py-1.5 border-b border-outline-variant">
                  <span className="text-on-surface-muted">Destination</span>
                  <span className="font-semibold text-on-surface">{pod.delivery_location_name || "Facility"}</span>
                </div>
                <div className="flex justify-between items-center py-1.5 border-b border-outline-variant">
                  <span className="text-on-surface-muted">Driver GPS Coordinates</span>
                  <span className="font-mono text-on-surface font-semibold">
                    {pod.latitude && pod.longitude ? `${pod.latitude.toFixed(5)}, ${pod.longitude.toFixed(5)}` : "Unavailable"}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1.5 border-b border-outline-variant">
                  <span className="text-on-surface-muted">Geofence Compliance</span>
                  <span className={`font-semibold px-2 py-0.5 rounded text-[11px] ${
                    pod.is_geofence_verified ? "bg-emerald-100 text-emerald-800" : "bg-surface-container text-on-surface"
                  }`}>
                    {pod.is_geofence_verified ? "Verified on Site ✓" : "Off-Geofence / Unconfirmed"}
                  </span>
                </div>
                {pod.distance_to_destination_meters !== null && pod.distance_to_destination_meters !== undefined && (
                  <div className="flex justify-between items-center py-1.5">
                    <span className="text-on-surface-muted">Distance to Dock</span>
                    <span className="font-semibold text-on-surface">
                      {Math.round(pod.distance_to_destination_meters)} meters
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Submitting Driver & Equipment */}
            <div className="bg-surface-card rounded-xl shadow-sm border border-outline-variant p-5 space-y-4">
              <h2 className="text-sm font-bold text-on-surface flex items-center gap-2">
                <Truck className="w-4 h-4 text-indigo-600" /> Transport Asset & Driver
              </h2>

              <div className="space-y-3 text-xs">
                <div className="flex justify-between items-center py-1.5 border-b border-outline-variant">
                  <span className="text-on-surface-muted">Delivering Driver</span>
                  <span className="font-semibold text-on-surface">{pod.driver_name || "Assigned Driver"}</span>
                </div>
                <div className="flex justify-between items-center py-1.5 border-b border-outline-variant">
                  <span className="text-on-surface-muted">Vehicle License Plate</span>
                  <span className="font-mono font-bold text-on-surface">{pod.vehicle_plate || "Assigned Vehicle"}</span>
                </div>
                <div className="flex justify-between items-center py-1.5">
                  <span className="text-on-surface-muted">Additional Remarks</span>
                  <span className="text-on-surface italic">{pod.additional_notes || "None"}</span>
                </div>
              </div>
            </div>

            {/* Review Status & Verification Audit */}
            <div className="bg-surface-card rounded-xl shadow-sm border border-outline-variant p-5 space-y-4">
              <h2 className="text-sm font-bold text-on-surface flex items-center gap-2">
                <FileText className="w-4 h-4 text-on-surface-muted" /> Verification Audit
              </h2>

              <div className="space-y-2.5 text-xs">
                <div className="flex justify-between py-1 border-b border-outline-variant">
                  <span className="text-on-surface-muted">Verified Timestamp</span>
                  <span className="font-semibold text-on-surface">
                    {pod.verified_at ? new Date(pod.verified_at).toLocaleString() : "Pending Signoff"}
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-outline-variant">
                  <span className="text-on-surface-muted">Expected Package Count</span>
                  <span className="font-semibold text-on-surface">{pod.expected_quantity} Units</span>
                </div>
                <div className="flex justify-between py-1 border-b border-outline-variant">
                  <span className="text-on-surface-muted">Received Package Count</span>
                  <span className={`font-semibold ${pod.is_shortage ? "text-red-600" : "text-on-success-container"}`}>
                    {pod.received_quantity} Units
                  </span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-on-surface-muted">Damage Condition</span>
                  <span className={`font-semibold ${pod.is_damaged ? "text-on-warning-container" : "text-on-success-container"}`}>
                    {pod.is_damaged ? `Damaged (${pod.damage_severity})` : "Clean Delivery ✓"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Rejection Modal */}
      {rejectModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-surface-card rounded-2xl max-w-md w-full p-6 shadow-2xl border border-outline-variant">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-on-surface flex items-center gap-2">
                <XCircle className="w-5 h-5 text-red-600" /> Reject Proof of Delivery
              </h3>
              <button onClick={() => setRejectModalOpen(false)} className="text-on-surface-subtle hover:text-on-surface-muted">
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-on-surface-muted mb-4">
              Rejecting proof of delivery returns the consignment for driver correction or claims investigation.
              A mandatory explanation is required.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-on-surface mb-1">
                  Rejection Reason <span className="text-red-500">*</span>
                </label>
                <textarea
                  rows={3}
                  required
                  placeholder="e.g. Blurry photo, signee signature does not match authorized receiver, cargo count disputed..."
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  className="w-full text-xs p-2.5 border border-outline-strong rounded-lg focus:ring-2 focus:ring-red-500 focus:outline-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setRejectModalOpen(false)}
                  className="px-4 py-2 rounded-lg border border-outline-strong text-xs font-medium hover:bg-surface-container-low"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={actionLoading || !rejectionReason.trim()}
                  onClick={() => handleReviewAction("REJECT")}
                  className="px-4 py-2 rounded-lg bg-red-600 text-white text-xs font-bold hover:bg-red-700 disabled:opacity-50"
                >
                  Confirm Rejection
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Photo Lightbox Modal */}
      {selectedPhoto && (
        <div
          onClick={() => setSelectedPhoto(null)}
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm cursor-zoom-out"
        >
          <div className="relative max-w-4xl max-h-[90vh] overflow-hidden rounded-xl bg-black">
            <img src={selectedPhoto} alt="High resolution delivery evidence" className="max-w-full max-h-[85vh] object-contain" />
            <button
              onClick={() => setSelectedPhoto(null)}
              className="absolute top-2 right-2 p-2 rounded-full bg-black/60 text-white hover:bg-black"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
