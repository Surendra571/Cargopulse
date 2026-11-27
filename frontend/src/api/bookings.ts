import { apiClient } from "@/lib/api-client";

// ============================================================================
// Enums & Types
// ============================================================================

export type BookingStatus =
  | "DRAFT"
  | "REQUESTED"
  | "PENDING_ACCEPTANCE"
  | "ACCEPTED"
  | "REJECTED"
  | "EXPIRED"
  | "CONFIRMED"
  | "CANCELLED";

export interface BookingVehicleSummary {
  id: string;
  license_plate: string;
  vehicle_type: string;
  capacity_kg: number;
  volume_cbm?: number | null;
  is_available: boolean;
  insurance_expiry?: string | null;
  fitness_expiry?: string | null;
}

export interface BookingDriverSummary {
  id: string;
  first_name: string;
  last_name: string;
  phone: string;
  license_number: string;
  license_expiry?: string | null;
  account_status: string;
}

export interface BookingTransporterSummary {
  id: string;
  name: string;
  code: string;
  phone: string;
  email?: string | null;
  verification_status: string;
  reliability_score: number;
}

export interface BookingShipmentSummary {
  id: string;
  tracking_number: string;
  status: string;
  customer_name?: string | null;
  origin_name: string;
  origin_city: string;
  origin_state: string;
  destination_name: string;
  destination_city: string;
  destination_state: string;
  total_weight_kg: number;
  required_vehicle_type: string;
  scheduled_pickup_time: string;
  expected_delivery_time: string;
}

export interface BookingMilestoneEvent {
  id: string;
  event_type: string;
  description: string;
  occurred_at: string;
  source: string;
}

export interface BookingAuditLogItem {
  id: string;
  action: string;
  user_email?: string | null;
  changes: Record<string, any>;
  created_at: string;
}

export interface BookingResponse {
  id: string;
  organization_id: string;
  booking_reference: string;
  status: BookingStatus;
  shipment_id: string;
  transporter_id: string;
  offered_rate?: number | null;
  agreed_rate?: number | null;
  expires_at: string;
  response_notes?: string | null;
  rejection_reason?: string | null;
  responded_at?: string | null;
  confirmed_at?: string | null;
  cancelled_at?: string | null;
  created_at: string;
  updated_at: string;

  shipment?: BookingShipmentSummary | null;
  transporter?: BookingTransporterSummary | null;
  vehicle?: BookingVehicleSummary | null;
  driver?: BookingDriverSummary | null;
  assignment_id?: string | null;
  is_expired: boolean;
}

export interface BookingDetailResponse extends BookingResponse {
  events: BookingMilestoneEvent[];
  audit_logs: BookingAuditLogItem[];
}

export interface BookingListResponse {
  items: BookingResponse[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Request Schemas
export interface BookingCreateRequest {
  shipment_id: string;
  transporter_id: string;
  offered_rate?: number | null;
  agreed_rate?: number | null;
  expires_in_hours?: number;
  vehicle_id?: string | null;
  driver_id?: string | null;
  booking_notes?: string | null;
}

export interface BookingAcceptRequest {
  agreed_rate?: number | null;
  response_notes?: string | null;
  vehicle_id?: string | null;
  driver_id?: string | null;
}

export interface BookingRejectRequest {
  rejection_reason: string;
  response_notes?: string | null;
}

export interface BookingAssignResourceRequest {
  vehicle_id: string;
  driver_id: string;
  notes?: string | null;
}

export interface BookingCancelRequest {
  cancellation_reason: string;
}

export interface BookingListQueryParams {
  page?: number;
  page_size?: number;
  shipment_id?: string;
  transporter_id?: string;
  status?: BookingStatus;
  search?: string;
}

// ============================================================================
// API Methods
// ============================================================================

export const bookingApi = {
  listBookings: async (params?: BookingListQueryParams): Promise<BookingListResponse> => {
    const res = await apiClient.get<BookingListResponse>("/bookings", { params });
    return res as any;
  },

  getBooking: async (bookingId: string): Promise<BookingDetailResponse> => {
    const res = await apiClient.get<BookingDetailResponse>(`/bookings/${bookingId}`);
    return res as any;
  },

  createBooking: async (payload: BookingCreateRequest): Promise<BookingResponse> => {
    const res = await apiClient.post<BookingResponse>("/bookings", payload);
    return res as any;
  },

  acceptBooking: async (
    bookingId: string,
    payload: BookingAcceptRequest
  ): Promise<BookingResponse> => {
    const res = await apiClient.post<BookingResponse>(`/bookings/${bookingId}/accept`, payload);
    return res as any;
  },

  rejectBooking: async (
    bookingId: string,
    payload: BookingRejectRequest
  ): Promise<BookingResponse> => {
    const res = await apiClient.post<BookingResponse>(`/bookings/${bookingId}/reject`, payload);
    return res as any;
  },

  assignResources: async (
    bookingId: string,
    payload: BookingAssignResourceRequest
  ): Promise<BookingResponse> => {
    const res = await apiClient.post<BookingResponse>(
      `/bookings/${bookingId}/assign-resources`,
      payload
    );
    return res as any;
  },

  cancelBooking: async (
    bookingId: string,
    payload: BookingCancelRequest
  ): Promise<BookingResponse> => {
    const res = await apiClient.post<BookingResponse>(`/bookings/${bookingId}/cancel`, payload);
    return res as any;
  },
};
