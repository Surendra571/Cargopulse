import { apiClient } from "@/lib/api-client";

export interface ShipmentListItem {
  id: string;
  organization_id: string;
  tracking_number: string;
  customer_name: string | null;
  customer_reference: string | null;
  status: string;
  priority: string;
  origin_name: string;
  origin_city: string;
  origin_state: string;
  destination_name: string;
  destination_city: string;
  destination_state: string;
  scheduled_pickup_time: string;
  expected_delivery_time: string;
  actual_pickup_time: string | null;
  actual_delivery_time: string | null;
  total_weight_kg: number;
  package_count: number;
  package_unit: string;
  required_vehicle_type: string;
  cargo_category: string;
  goods_description?: string;
  is_hazardous: boolean;
  assigned_transporter_id: string | null;
  assigned_transporter_name: string | null;
  open_exceptions_count: number;
  created_at: string;
}

export interface PaginatedShipmentsResponse {
  items: ShipmentListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface TransporterBookingSummary {
  id: string;
  transporter_id: string;
  transporter_name: string;
  transporter_code: string;
  status: string;
  offered_rate: number | null;
  agreed_rate: number | null;
  expires_at: string | null;
  created_at: string;
}

export interface ShipmentEventResponse {
  id: string;
  event_type: string;
  description: string;
  occurred_at: string;
  location_name: string | null;
  source: string;
  created_by_user_id: string | null;
}

export interface ShipmentExceptionSummary {
  id: string;
  exception_type: string;
  severity: string;
  status: string;
  title: string;
  description: string;
  reported_at: string;
  resolved_at: string | null;
  resolution_notes: string | null;
}

export interface ProofOfDeliverySummary {
  id: string;
  signed_by_name: string | null;
  signed_at: string | null;
  document_url: string | null;
  is_verified: boolean;
}

export interface ShipmentAuditLogItem {
  id: string;
  action: string;
  performed_at: string;
  user_email: string | null;
  old_values?: Record<string, any> | null;
  new_values?: Record<string, any> | null;
}

export interface ShipmentDetailResponse {
  id: string;
  organization_id: string;
  tracking_number: string;
  status: string;
  priority: string;
  customer_name: string | null;
  customer_reference: string | null;
  cargo_category: string;
  goods_description: string;
  total_weight_kg: number;
  package_count: number;
  package_unit: string;
  total_volume_cbm: number | null;
  required_vehicle_type: string;
  is_hazardous: boolean;

  origin_name: string;
  origin_address: string;
  origin_city: string;
  origin_state: string;
  origin_postal_code: string;
  origin_dock_number: string | null;
  origin_contact_name: string;
  origin_contact_phone: string;

  destination_name: string;
  destination_address: string;
  destination_city: string;
  destination_state: string;
  destination_postal_code: string;
  destination_dock_number: string | null;
  destination_contact_name: string;
  destination_contact_phone: string;

  scheduled_pickup_time: string;
  expected_delivery_time: string;
  actual_pickup_time: string | null;
  actual_delivery_time: string | null;

  special_instructions: string | null;
  invoice_number: string | null;
  invoice_value: number | null;
  custom_metadata: Record<string, any> | null;

  assigned_transporter_id: string | null;
  assigned_transporter_name: string | null;
  assigned_driver_name: string | null;
  assigned_vehicle_plate: string | null;

  bookings: TransporterBookingSummary[];
  events: ShipmentEventResponse[];
  exceptions: ShipmentExceptionSummary[];
  audit_history: ShipmentAuditLogItem[];
  pod_verified: boolean;
  pod_signatory_name: string | null;
  pod_signed_at: string | null;
  pod_document_url: string | null;

  created_at: string;
  updated_at: string;
}

export interface ShipmentCreateRequest {
  customer_name: string;
  customer_reference?: string;
  origin_name: string;
  origin_address: string;
  origin_city: string;
  origin_state: string;
  origin_postal_code: string;
  origin_dock_number?: string;
  origin_contact_name: string;
  origin_contact_phone: string;
  destination_name: string;
  destination_address: string;
  destination_city: string;
  destination_state: string;
  destination_postal_code: string;
  destination_dock_number?: string;
  destination_contact_name: string;
  destination_contact_phone: string;
  goods_description: string;
  cargo_category: string;
  total_weight_kg: number;
  package_count: number;
  package_unit: string;
  total_volume_cbm?: number;
  required_vehicle_type: string;
  is_hazardous: boolean;
  scheduled_pickup_time: string;
  expected_delivery_time: string;
  priority: string;
  special_instructions?: string;
  invoice_number?: string;
  invoice_value?: number;
}

export interface ShipmentUpdateRequest {
  customer_name?: string;
  customer_reference?: string;
  origin_name?: string;
  origin_address?: string;
  origin_city?: string;
  origin_state?: string;
  origin_postal_code?: string;
  origin_dock_number?: string;
  origin_contact_name?: string;
  origin_contact_phone?: string;
  destination_name?: string;
  destination_address?: string;
  destination_city?: string;
  destination_state?: string;
  destination_postal_code?: string;
  destination_dock_number?: string;
  destination_contact_name?: string;
  destination_contact_phone?: string;
  goods_description?: string;
  cargo_category?: string;
  total_weight_kg?: number;
  package_count?: number;
  package_unit?: string;
  total_volume_cbm?: number;
  required_vehicle_type?: string;
  is_hazardous?: boolean;
  scheduled_pickup_time?: string;
  expected_delivery_time?: string;
  priority?: string;
  special_instructions?: string;
  invoice_number?: string;
  invoice_value?: number;
}

export interface ShipmentCancelRequest {
  cancellation_reason: string;
}

export interface ShipmentListParams {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  priority?: string;
  start_date?: string;
  end_date?: string;
  sort_by?: string;
  sort_order?: string;
}

export const shipmentApi = {
  async createShipment(data: ShipmentCreateRequest): Promise<ShipmentDetailResponse> {
    const res = await apiClient.post<ShipmentDetailResponse>("/api/v1/shipments", data);
    return res as any;
  },

  async listShipments(params?: ShipmentListParams): Promise<PaginatedShipmentsResponse> {
    const res = await apiClient.get<PaginatedShipmentsResponse>("/api/v1/shipments", { params });
    return res as any;
  },

  async getShipment(id: string): Promise<ShipmentDetailResponse> {
    const res = await apiClient.get<ShipmentDetailResponse>(`/api/v1/shipments/${id}`);
    return res as any;
  },

  async updateShipment(id: string, data: ShipmentUpdateRequest): Promise<ShipmentDetailResponse> {
    const res = await apiClient.put<ShipmentDetailResponse>(`/api/v1/shipments/${id}`, data);
    return res as any;
  },

  async cancelShipment(id: string, data: ShipmentCancelRequest): Promise<ShipmentDetailResponse> {
    const res = await apiClient.post<ShipmentDetailResponse>(`/api/v1/shipments/${id}/cancel`, data);
    return res as any;
  },
};
