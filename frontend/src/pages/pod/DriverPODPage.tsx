import React, { useEffect, useRef, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  Camera,
  CheckCircle2,
  AlertTriangle,
  MapPin,
  PenTool,
  ArrowLeft,
  X,
  ShieldCheck,
  PackageCheck,
  FileText,
  Loader2,
} from "lucide-react";
import { shipmentApi } from "@/api/shipments";
import { uploadPODFile, submitPOD, ProofOfDelivery } from "@/api/pod";

export const DriverPODPage: React.FC = () => {
  const { shipmentId } = useParams<{ shipmentId: string }>();
  const navigate = useNavigate();

  // Shipment metadata
  const [shipment, setShipment] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submittedPOD, setSubmittedPOD] = useState<ProofOfDelivery | null>(null);

  // Form Fields
  const [recipientName, setRecipientName] = useState("");
  const [recipientDesignation, setRecipientDesignation] = useState("");
  const [recipientPhone, setRecipientPhone] = useState("");
  const [recipientEmail, setRecipientEmail] = useState("");
  const [receivedQuantity, setReceivedQuantity] = useState<number>(0);
  const [expectedQuantity, setExpectedQuantity] = useState<number>(1);
  const [acknowledgementType] = useState("DIGITAL_SIGNATURE");
  const [additionalNotes, setAdditionalNotes] = useState("");

  // Location
  const [latitude, setLatitude] = useState<number | null>(null);
  const [longitude, setLongitude] = useState<number | null>(null);
  const [locationName, setLocationName] = useState("");
  const [locating, setLocating] = useState(false);

  // Evidence Photos
  const [deliveryPhotos, setDeliveryPhotos] = useState<Array<{ key: string; url: string; name: string }>>([]);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);

  // Damage
  const [isDamaged, setIsDamaged] = useState(false);
  const [damageSeverity, setDamageSeverity] = useState("MODERATE");
  const [damageDescription, setDamageDescription] = useState("");
  const [damagePhotos, setDamagePhotos] = useState<Array<{ key: string; url: string; name: string }>>([]);
  const [uploadingDamagePhoto, setUploadingDamagePhoto] = useState(false);

  // Signature Canvas
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [hasSignature, setHasSignature] = useState(false);
  const [signatureUrl, setSignatureUrl] = useState<string | null>(null);
  const [uploadingSig, setUploadingSig] = useState(false);

  useEffect(() => {
    if (!shipmentId) return;
    const fetchShipmentData = async () => {
      setLoading(true);
      try {
        const data = await shipmentApi.getShipment(shipmentId);
        setShipment(data);
        const qty = data.package_count || 1;
        setExpectedQuantity(qty);
        setReceivedQuantity(qty);
        if (data.destination_name || data.destination_city) {
          setLocationName(`${data.destination_name || ''} - ${data.destination_city || ''}`.trim());
        }
      } catch (err: any) {
        setError(err.response?.data?.detail || "Failed to load shipment details.");
      } finally {
        setLoading(false);
      }
    };
    fetchShipmentData();
  }, [shipmentId]);

  // Geolocation capture
  const handleCaptureGPS = () => {
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by your mobile browser.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLatitude(pos.coords.latitude);
        setLongitude(pos.coords.longitude);
        setLocating(false);
      },
      (err) => {
        console.warn("GPS error:", err);
        setLocating(false);
        alert("Could not access GPS location. Please ensure location permissions are granted.");
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  // Canvas drawing handlers
  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    setIsDrawing(true);
    const rect = canvas.getBoundingClientRect();
    const x = ("touches" in e) ? e.touches[0].clientX - rect.left : e.clientX - rect.left;
    const y = ("touches" in e) ? e.touches[0].clientY - rect.top : e.clientY - rect.top;

    ctx.beginPath();
    ctx.moveTo(x, y);
  };

  const draw = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    if (!isDrawing) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const x = ("touches" in e) ? e.touches[0].clientX - rect.left : e.clientX - rect.left;
    const y = ("touches" in e) ? e.touches[0].clientY - rect.top : e.clientY - rect.top;

    ctx.lineTo(x, y);
    ctx.strokeStyle = "#0f172a";
    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    ctx.stroke();
    setHasSignature(true);
  };

  const stopDrawing = () => {
    setIsDrawing(false);
  };

  const clearSignature = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasSignature(false);
    setSignatureUrl(null);
  };

  // Upload delivery photograph
  const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>, isDamage: boolean = false) => {
    if (!e.target.files || e.target.files.length === 0 || !shipmentId) return;
    const file = e.target.files[0];

    // File validation check
    if (file.size > 10 * 1024 * 1024) {
      alert("File exceeds maximum size of 10MB.");
      return;
    }

    if (isDamage) {
      setUploadingDamagePhoto(true);
    } else {
      setUploadingPhoto(true);
    }

    try {
      const res = await uploadPODFile(shipmentId, file, isDamage ? "damage_photo" : "delivery_photo");
      const item = {
        key: res.file.file_key,
        url: res.file.url,
        name: res.file.file_name,
      };

      if (isDamage) {
        setDamagePhotos((prev) => [...prev, item]);
      } else {
        setDeliveryPhotos((prev) => [...prev, item]);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || "Upload failed. Please try again.");
    } finally {
      if (isDamage) setUploadingDamagePhoto(false);
      else setUploadingPhoto(false);
      e.target.value = "";
    }
  };

  // Convert canvas to blob and upload signature
  const uploadSignatureCanvas = async (): Promise<string | null> => {
    if (signatureUrl) return signatureUrl;
    const canvas = canvasRef.current;
    if (!canvas || !hasSignature || !shipmentId) return null;

    setUploadingSig(true);
    return new Promise((resolve) => {
      canvas.toBlob(async (blob) => {
        if (!blob) {
          setUploadingSig(false);
          resolve(null);
          return;
        }
        try {
          const file = new File([blob], "recipient_signature.png", { type: "image/png" });
          const res = await uploadPODFile(shipmentId, file, "signature");
          setSignatureUrl(res.file.url);
          resolve(res.file.url);
        } catch (err) {
          console.error("Signature upload failed", err);
          resolve(null);
        } finally {
          setUploadingSig(false);
        }
      }, "image/png");
    });
  };

  // Submit complete POD
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!shipmentId) return;
    setError(null);

    if (!recipientName.trim()) {
      setError("Recipient / Signee Name is strictly required.");
      return;
    }

    if (deliveryPhotos.length === 0) {
      setError("At least one delivery photograph (dock, cargo, or facility) is required.");
      return;
    }

    if (!hasSignature && !signatureUrl) {
      setError("Recipient digital signature or acknowledgement signoff is required.");
      return;
    }

    setSubmitting(true);
    try {
      const uploadedSigUrl = await uploadSignatureCanvas();
      if (!uploadedSigUrl) {
        throw new Error("Failed to process signature image.");
      }

      const payload = {
        recipient_name: recipientName.trim(),
        recipient_designation: recipientDesignation.trim() || undefined,
        recipient_phone: recipientPhone.trim() || undefined,
        recipient_email: recipientEmail.trim() || undefined,
        received_quantity: receivedQuantity,
        acknowledgement_type: acknowledgementType,
        signature_image_url: uploadedSigUrl,
        delivery_photo_urls: deliveryPhotos.map((p) => p.url),
        latitude: latitude || undefined,
        longitude: longitude || undefined,
        delivery_location_name: locationName.trim() || undefined,
        is_damaged: isDamaged,
        damage_severity: isDamaged ? damageSeverity : undefined,
        damage_description: isDamaged ? damageDescription.trim() || undefined : undefined,
        damage_photo_urls: isDamaged ? damagePhotos.map((p) => p.url) : [],
        shortage_description: receivedQuantity < expectedQuantity ? `Shortage: Received ${receivedQuantity} of ${expectedQuantity} units.` : undefined,
        additional_notes: additionalNotes.trim() || undefined,
      };

      const result = await submitPOD(shipmentId, payload);
      setSubmittedPOD(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Failed to submit Proof of Delivery.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-surface-container-low flex items-center justify-center p-4">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <p className="text-sm font-medium text-on-surface-muted">Loading delivery details...</p>
        </div>
      </div>
    );
  }

  // Success view
  if (submittedPOD) {
    const isClean = submittedPOD.verification_status === "VERIFIED" || submittedPOD.verification_status === "PENDING";
    return (
      <div className="min-h-screen bg-surface-container-low py-8 px-4 sm:px-6">
        <div className="max-w-lg mx-auto bg-surface-card rounded-2xl shadow-xl border border-outline-variant p-6 sm:p-8 text-center">
          <div className={`w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4 ${
            isClean ? "bg-emerald-100 text-success" : "bg-amber-100 text-warning"
          }`}>
            {isClean ? <CheckCircle2 className="w-10 h-10" /> : <AlertTriangle className="w-10 h-10" />}
          </div>

          <h2 className="text-2xl font-bold text-on-surface mb-1">
            {isClean ? "Delivery Recorded Successfully!" : "POD Submitted with Discrepancy"}
          </h2>
          <p className="text-sm text-on-surface-muted mb-6">
            Shipment Reference: <span className="font-semibold text-on-surface">{submittedPOD.tracking_number}</span>
          </p>

          <div className="bg-surface-container-low rounded-xl p-4 mb-6 text-left space-y-2 text-sm border border-outline-variant">
            <div className="flex justify-between py-1 border-b border-outline-variant">
              <span className="text-on-surface-muted">Status</span>
              <span className={`font-semibold px-2 py-0.5 rounded text-xs ${
                submittedPOD.verification_status === "VERIFIED"
                  ? "bg-emerald-100 text-emerald-800"
                  : submittedPOD.verification_status === "DISCREPANCY_FLAGGED"
                  ? "bg-amber-100 text-amber-800"
                  : "bg-primary-container text-on-primary-container"
              }`}>
                {submittedPOD.verification_status}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-outline-variant">
              <span className="text-on-surface-muted">Signed By</span>
              <span className="font-medium text-on-surface">{submittedPOD.signed_by_name}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-outline-variant">
              <span className="text-on-surface-muted">Packages Received</span>
              <span className="font-medium text-on-surface">
                {submittedPOD.received_quantity} / {submittedPOD.expected_quantity}
              </span>
            </div>
            {submittedPOD.is_shortage && (
              <div className="flex justify-between py-1 text-red-600 font-medium">
                <span>Shortage</span>
                <span>-{submittedPOD.shortage_quantity} packages</span>
              </div>
            )}
            {submittedPOD.is_damaged && (
              <div className="flex justify-between py-1 text-on-warning-container font-medium">
                <span>Damage</span>
                <span>{submittedPOD.damage_severity} Severity</span>
              </div>
            )}
          </div>

          <div className="space-y-3">
            <Link
              to={`/pod/review/${shipmentId}`}
              className="w-full inline-flex justify-center items-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-white font-medium hover:bg-burnt-orange transition"
            >
              <FileText className="w-4 h-4" /> View Complete POD Certificate
            </Link>
            <Link
              to={`/tracking/${shipmentId}`}
              className="w-full inline-flex justify-center items-center gap-2 px-4 py-2.5 rounded-lg border border-outline-strong text-on-surface font-medium hover:bg-surface-container-low transition"
            >
              Back to Shipment Tracking
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const isShortage = receivedQuantity < expectedQuantity;

  return (
    <div className="min-h-screen bg-surface-container pb-12">
      {/* Mobile-Friendly Sticky Top Bar */}
      <div className="sticky top-0 z-30 bg-surface-card border-b border-outline-variant shadow-sm px-4 py-3">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <button
            onClick={() => navigate(-1)}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-on-surface-muted hover:text-on-surface"
          >
            <ArrowLeft className="w-4 h-4" /> Back
          </button>
          <div className="text-right">
            <span className="text-xs text-on-surface-subtle block">ePOD Capture</span>
            <span className="text-sm font-bold text-on-surface">{shipment?.tracking_number}</span>
          </div>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 pt-6 space-y-6">
        {/* Shipment Destination & Consignee Summary Card */}
        <div className="bg-surface-card rounded-xl shadow-sm border border-outline-variant p-4 sm:p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-primary-container text-primary flex items-center justify-center font-bold">
              <PackageCheck className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-on-surface">Proof of Delivery</h1>
              <p className="text-xs text-on-surface-muted">Capture verifiable delivery evidence at drop-off</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs pt-3 border-t border-outline-variant">
            <div>
              <span className="text-on-surface-subtle block">Destination Facility</span>
              <span className="font-semibold text-on-surface">{shipment?.destination_name || "Consignee Dock"}</span>
              <p className="text-on-surface-muted">{shipment?.destination_city}, {shipment?.destination_state}</p>
            </div>
            <div>
              <span className="text-on-surface-subtle block">Expected Cargo</span>
              <span className="font-semibold text-on-surface">{expectedQuantity} Packages</span>
              <p className="text-on-surface-muted">{shipment?.goods_description || "Freight items"}</p>
            </div>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3 text-sm text-red-700">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5 text-red-500" />
            <div>
              <span className="font-semibold">Submission Incomplete</span>
              <p className="mt-0.5">{error}</p>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* STEP 1: Recipient Information */}
          <div className="bg-surface-card rounded-xl shadow-sm border border-outline-variant p-4 sm:p-5 space-y-4">
            <h2 className="text-sm font-bold text-on-surface flex items-center gap-2">
              <span className="w-6 h-6 rounded-full bg-primary-container text-primary text-xs flex items-center justify-center font-bold">1</span>
              Recipient Information
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-on-surface mb-1">
                  Recipient Full Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. John Doe"
                  value={recipientName}
                  onChange={(e) => setRecipientName(e.target.value)}
                  className="w-full text-sm px-3 py-2 border border-outline-strong rounded-lg focus:ring-2 focus:ring-burnt-orange focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-on-surface mb-1">
                  Designation / Role
                </label>
                <input
                  type="text"
                  placeholder="e.g. Warehouse Receiver"
                  value={recipientDesignation}
                  onChange={(e) => setRecipientDesignation(e.target.value)}
                  className="w-full text-sm px-3 py-2 border border-outline-strong rounded-lg focus:ring-2 focus:ring-burnt-orange focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-on-surface mb-1">
                  Recipient Phone
                </label>
                <input
                  type="tel"
                  placeholder="+1-555-0123"
                  value={recipientPhone}
                  onChange={(e) => setRecipientPhone(e.target.value)}
                  className="w-full text-sm px-3 py-2 border border-outline-strong rounded-lg focus:ring-2 focus:ring-burnt-orange focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-on-surface mb-1">
                  Recipient Email
                </label>
                <input
                  type="email"
                  placeholder="receiver@facility.com"
                  value={recipientEmail}
                  onChange={(e) => setRecipientEmail(e.target.value)}
                  className="w-full text-sm px-3 py-2 border border-outline-strong rounded-lg focus:ring-2 focus:ring-burnt-orange focus:outline-none"
                />
              </div>
            </div>
          </div>

          {/* STEP 2: Quantity & Shortage Verification */}
          <div className="bg-surface-card rounded-xl shadow-sm border border-outline-variant p-4 sm:p-5 space-y-4">
            <h2 className="text-sm font-bold text-on-surface flex items-center gap-2">
              <span className="w-6 h-6 rounded-full bg-primary-container text-primary text-xs flex items-center justify-center font-bold">2</span>
              Quantity Received Verification
            </h2>

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-3 bg-surface-container-low rounded-lg border border-outline-variant">
              <div>
                <span className="text-xs text-on-surface-muted block">Expected Manifest Quantity</span>
                <span className="text-lg font-bold text-on-surface">{expectedQuantity} Units</span>
              </div>

              <div className="flex items-center gap-2">
                <label className="text-xs font-medium text-on-surface">Actual Received:</label>
                <input
                  type="number"
                  min={0}
                  required
                  value={receivedQuantity}
                  onChange={(e) => setReceivedQuantity(parseInt(e.target.value) || 0)}
                  className="w-24 text-center font-bold text-base px-2 py-1.5 border border-outline-strong rounded-lg focus:ring-2 focus:ring-burnt-orange"
                />
              </div>
            </div>

            {isShortage && (
              <div className="p-3 bg-warning-container border border-amber-200 rounded-lg flex items-start gap-2.5 text-xs text-amber-800">
                <AlertTriangle className="w-4 h-4 text-warning flex-shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold">Quantity Discrepancy Detected!</span>
                  <p>
                    Missing <span className="font-bold">{expectedQuantity - receivedQuantity} packages</span>. A delivery shortage exception and discrepancy claim will be automatically created.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* STEP 3: Digital Signature / Signoff */}
          <div className="bg-surface-card rounded-xl shadow-sm border border-outline-variant p-4 sm:p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-on-surface flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary-container text-primary text-xs flex items-center justify-center font-bold">3</span>
                Recipient Signature <span className="text-red-500">*</span>
              </h2>
              {hasSignature && (
                <button
                  type="button"
                  onClick={clearSignature}
                  className="text-xs text-red-600 hover:text-red-800 font-medium"
                >
                  Clear Signature
                </button>
              )}
            </div>
            <p className="text-xs text-on-surface-muted">Sign directly on the touch screen or canvas below</p>

            <div className="border-2 border-dashed border-outline-strong rounded-xl overflow-hidden bg-surface-card touch-none">
              <canvas
                ref={canvasRef}
                width={500}
                height={160}
                onMouseDown={startDrawing}
                onMouseMove={draw}
                onMouseUp={stopDrawing}
                onMouseLeave={stopDrawing}
                onTouchStart={startDrawing}
                onTouchMove={draw}
                onTouchEnd={stopDrawing}
                className="w-full h-40 cursor-crosshair block"
              />
            </div>
            <div className="flex items-center justify-between text-xs text-on-surface-subtle">
              <span className="flex items-center gap-1">
                <PenTool className="w-3.5 h-3.5" /> Sign inside the box
              </span>
              <span>{hasSignature ? "Signature captured ✓" : "Awaiting signature"}</span>
            </div>
          </div>

          {/* STEP 4: Photographic Delivery Proof */}
          <div className="bg-surface-card rounded-xl shadow-sm border border-outline-variant p-4 sm:p-5 space-y-4">
            <h2 className="text-sm font-bold text-on-surface flex items-center gap-2">
              <span className="w-6 h-6 rounded-full bg-primary-container text-primary text-xs flex items-center justify-center font-bold">4</span>
              Delivery Photographs <span className="text-red-500">*</span>
            </h2>
            <p className="text-xs text-on-surface-muted">
              Capture at least one clear photo of cargo unloaded at the facility dock or gate
            </p>

            {/* Photo Previews */}
            {deliveryPhotos.length > 0 && (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {deliveryPhotos.map((photo, idx) => (
                  <div key={idx} className="relative rounded-lg overflow-hidden border border-outline-variant group bg-surface-container-low">
                    <img src={photo.url} alt="Delivery evidence" className="w-full h-28 object-cover" />
                    <button
                      type="button"
                      onClick={() => setDeliveryPhotos((prev) => prev.filter((_, i) => i !== idx))}
                      className="absolute top-1 right-1 p-1 bg-red-600 text-white rounded-full opacity-90 hover:opacity-100 shadow"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                    <span className="text-[10px] text-on-surface-muted px-2 py-0.5 truncate block">{photo.name}</span>
                  </div>
                ))}
              </div>
            )}

            <label className="flex flex-col items-center justify-center border-2 border-dashed border-outline-strong hover:border-burnt-orange rounded-xl p-4 cursor-pointer bg-surface-container-low hover:bg-primary-container/50 transition">
              <div className="flex items-center gap-2 text-primary font-medium text-xs">
                {uploadingPhoto ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> Uploading to secure storage...
                  </>
                ) : (
                  <>
                    <Camera className="w-4 h-4" /> Take Photo / Select Image
                  </>
                )}
              </div>
              <span className="text-[11px] text-on-surface-subtle mt-1">JPEG, PNG, WebP up to 10MB</span>
              <input
                type="file"
                accept="image/*"
                capture="environment"
                disabled={uploadingPhoto}
                onChange={(e) => handlePhotoUpload(e, false)}
                className="hidden"
              />
            </label>
          </div>

          {/* STEP 5: Cargo Damage Report (Optional Toggle) */}
          <div className="bg-surface-card rounded-xl shadow-sm border border-outline-variant p-4 sm:p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-on-surface flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-surface-container text-on-surface text-xs flex items-center justify-center font-bold">5</span>
                  Cargo Damage Report
                </h2>
                <p className="text-xs text-on-surface-muted">Only enable if packages were crushed, broken, or leaked</p>
              </div>

              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={isDamaged}
                  onChange={(e) => setIsDamaged(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-surface-container peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-surface-card after:border-outline-strong after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-red-600"></div>
              </label>
            </div>

            {isDamaged && (
              <div className="p-4 bg-red-50/60 border border-red-200 rounded-xl space-y-3">
                <div>
                  <label className="block text-xs font-semibold text-on-surface mb-1">
                    Damage Severity Level
                  </label>
                  <select
                    value={damageSeverity}
                    onChange={(e) => setDamageSeverity(e.target.value)}
                    className="w-full text-xs px-3 py-2 border border-outline-strong rounded-lg bg-surface-card"
                  >
                    <option value="MINOR">Minor (Scuffed carton, contents intact)</option>
                    <option value="MODERATE">Moderate (Torn wrapping, pallet leaning)</option>
                    <option value="SEVERE">Severe (Crushed packaging, visible destruction)</option>
                    <option value="TOTAL_LOSS">Total Loss (Consignment completely rejected)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-on-surface mb-1">
                    Detailed Description of Damage
                  </label>
                  <textarea
                    rows={2}
                    placeholder="Describe specific items affected and nature of damage..."
                    value={damageDescription}
                    onChange={(e) => setDamageDescription(e.target.value)}
                    className="w-full text-xs px-3 py-2 border border-outline-strong rounded-lg focus:outline-none focus:ring-1 focus:ring-red-500"
                  />
                </div>

                {/* Damage Photos */}
                <div>
                  <label className="block text-xs font-semibold text-on-surface mb-1">
                    Damage Photographic Proof
                  </label>
                  {damagePhotos.length > 0 && (
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-2">
                      {damagePhotos.map((photo, idx) => (
                        <div key={idx} className="relative rounded overflow-hidden border border-red-200">
                          <img src={photo.url} alt="Damage evidence" className="w-full h-20 object-cover" />
                          <button
                            type="button"
                            onClick={() => setDamagePhotos((prev) => prev.filter((_, i) => i !== idx))}
                            className="absolute top-1 right-1 p-0.5 bg-red-600 text-white rounded-full"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  <label className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-300 bg-surface-card text-xs text-red-700 cursor-pointer hover:bg-red-50">
                    {uploadingDamagePhoto ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Camera className="w-3.5 h-3.5" />}
                    Upload Damage Photo
                    <input
                      type="file"
                      accept="image/*"
                      capture="environment"
                      disabled={uploadingDamagePhoto}
                      onChange={(e) => handlePhotoUpload(e, true)}
                      className="hidden"
                    />
                  </label>
                </div>
              </div>
            )}
          </div>

          {/* STEP 6: Geolocation & Final Notes */}
          <div className="bg-surface-card rounded-xl shadow-sm border border-outline-variant p-4 sm:p-5 space-y-4">
            <h2 className="text-sm font-bold text-on-surface flex items-center gap-2">
              <span className="w-6 h-6 rounded-full bg-surface-container text-on-surface text-xs flex items-center justify-center font-bold">6</span>
              Delivery Location & Verification
            </h2>

            <div className="flex items-center justify-between p-3 bg-surface-container-low rounded-lg border border-outline-variant">
              <div>
                <span className="text-xs text-on-surface-muted block">GPS Coordinates</span>
                <span className="text-xs font-mono font-semibold text-on-surface">
                  {latitude && longitude ? `${latitude.toFixed(5)}, ${longitude.toFixed(5)}` : "Not captured"}
                </span>
              </div>
              <button
                type="button"
                onClick={handleCaptureGPS}
                disabled={locating}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-outline-strong text-xs font-medium bg-surface-card hover:bg-surface-container-low text-on-surface shadow-sm"
              >
                {locating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <MapPin className="w-3.5 h-3.5 text-primary" />}
                {latitude ? "Update GPS" : "Capture GPS"}
              </button>
            </div>

            <div>
              <label className="block text-xs font-medium text-on-surface mb-1">
                Additional Delivery Notes / Comments
              </label>
              <textarea
                rows={2}
                placeholder="Gate code, receiving bay number, or remarks..."
                value={additionalNotes}
                onChange={(e) => setAdditionalNotes(e.target.value)}
                className="w-full text-xs px-3 py-2 border border-outline-strong rounded-lg focus:ring-2 focus:ring-burnt-orange focus:outline-none"
              />
            </div>
          </div>

          {/* Action Buttons */}
          <div className="space-y-3 pt-2">
            <button
              type="submit"
              disabled={submitting || uploadingPhoto || uploadingSig}
              className={`w-full py-3.5 px-4 rounded-xl text-white font-bold text-sm shadow-lg flex items-center justify-center gap-2 transition ${
                isDamaged || isShortage
                  ? "bg-amber-600 hover:bg-amber-700 shadow-amber-600/20"
                  : "bg-primary hover:bg-burnt-orange shadow-blue-600/20"
              }`}
            >
              {submitting ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" /> Submitting Verifiable Evidence...
                </>
              ) : (
                <>
                  <ShieldCheck className="w-5 h-5" />
                  {isDamaged || isShortage ? "Submit POD with Discrepancies" : "Submit Complete Proof of Delivery"}
                </>
              )}
            </button>
            <p className="text-[11px] text-center text-on-surface-subtle">
              By submitting, you certify that cargo details, quantities, and digital signoffs are true and accurate.
            </p>
          </div>
        </form>
      </div>
    </div>
  );
};
