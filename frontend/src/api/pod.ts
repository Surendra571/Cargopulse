import { apiClient } from "@/lib/api-client";

export type PODVerificationStatus =
  | "PENDING"
  | "VERIFIED"
  | "REJECTED"
  | "DISCREPANCY_FLAGGED";

export interface StoredFileSummary {
  file_key: string;
  file_name: string;
  content_type: string;
  file_size_bytes: number;
  sha256_hash: string;
  storage_provider: string;
  url: string;
  uploaded_at: string;
  category: string;
}

export interface PODUploadResponse {
  success: boolean;
  file: StoredFileSummary;
}

export interface DiscrepancyItem {
  id: string;
  pod_id: string;
  discrepancy_type: string;
  status: string;
  item_name: string;
  expected_quantity: number;
  received_quantity: number;
  variance: number;
  notes?: string | null;
  evidence_image_urls: string[];
}

export interface ProofOfDelivery {
  id: string;
  organization_id: string;
  shipment_id: string;
  tracking_number?: string | null;
  verification_status: PODVerificationStatus;
  
  signed_by_name: string;
  signed_by_designation?: string | null;
  recipient_phone?: string | null;
  recipient_email?: string | null;
  signed_at: string;
  
  expected_quantity: number;
  received_quantity: number;
  is_shortage: boolean;
  shortage_quantity: number;
  shortage_description?: string | null;
  
  is_damaged: boolean;
  damage_severity?: string | null;
  damage_description?: string | null;
  damage_photo_urls: string[];
  
  signature_image_url?: string | null;
  document_url?: string | null;
  delivery_photo_urls: string[];
  
  driver_id?: string | null;
  vehicle_id?: string | null;
  driver_name?: string | null;
  vehicle_plate?: string | null;
  acknowledgement_type: string;
  additional_notes?: string | null;
  
  latitude?: number | null;
  longitude?: number | null;
  delivery_location_name?: string | null;
  distance_to_destination_meters?: number | null;
  is_geofence_verified: boolean;
  
  verified_at?: string | null;
  verified_by_user_id?: string | null;
  rejection_reason?: string | null;
  
  file_metadata: Record<string, any>;
  submission_history: Array<{
    revision: number;
    action: string;
    timestamp: string;
    submitted_by_email?: string;
    reviewed_by_email?: string;
    notes?: string;
    rejection_reason?: string;
    [key: string]: any;
  }>;
  discrepancies: DiscrepancyItem[];
  is_modified: boolean;
  
  created_at: string;
  updated_at: string;
}

export interface DriverPODSubmissionRequest {
  recipient_name: string;
  recipient_designation?: string;
  recipient_phone?: string;
  recipient_email?: string;
  delivered_at?: string;
  received_quantity: number;
  acknowledgement_type?: string;
  signature_image_url?: string;
  document_url?: string;
  delivery_photo_urls: string[];
  latitude?: number;
  longitude?: number;
  delivery_location_name?: string;
  is_damaged?: boolean;
  damage_severity?: string;
  damage_description?: string;
  damage_photo_urls?: string[];
  shortage_description?: string;
  additional_notes?: string;
}

export interface ManufacturerPODReviewRequest {
  action: "APPROVE" | "REJECT" | "FLAG_DISCREPANCY";
  rejection_reason?: string;
  notes?: string;
}

export interface PODListParams {
  page?: number;
  page_size?: number;
  status?: string;
  is_damaged?: boolean;
  is_shortage?: boolean;
  search?: string;
}

export interface PODListResponse {
  items: ProofOfDelivery[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// ============================================================================
// API Methods
// ============================================================================

export async function uploadPODFile(
  shipmentId: string,
  file: File,
  category: string = "delivery_photo"
): Promise<PODUploadResponse> {
  const formData = new FormData();
  formData.append("shipment_id", shipmentId);
  formData.append("category", category);
  formData.append("file", file);

  const res = await apiClient.post<PODUploadResponse>("/api/v1/pod/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return res as any;
}

export async function submitPOD(
  shipmentId: string,
  data: DriverPODSubmissionRequest
): Promise<ProofOfDelivery> {
  const res = await apiClient.post<ProofOfDelivery>(
    `/api/v1/pod/shipments/${shipmentId}/submit`,
    data
  );
  return res as any;
}

export async function reviewPOD(
  shipmentId: string,
  data: ManufacturerPODReviewRequest
): Promise<ProofOfDelivery> {
  const res = await apiClient.post<ProofOfDelivery>(
    `/api/v1/pod/shipments/${shipmentId}/review`,
    data
  );
  return res as any;
}

export async function getShipmentPOD(shipmentId: string): Promise<ProofOfDelivery> {
  const res = await apiClient.get<ProofOfDelivery>(
    `/api/v1/pod/shipments/${shipmentId}`
  );
  return res as any;
}

export async function listPODs(params?: PODListParams): Promise<PODListResponse> {
  const res = await apiClient.get<PODListResponse>("/api/v1/pod", { params });
  return res as any;
}
