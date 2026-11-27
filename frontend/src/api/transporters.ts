import { apiClient } from "@/lib/api-client";

// ============================================================================
// Types & Interfaces
// ============================================================================

export type TransporterVerificationStatus =
  | "REGISTERED"
  | "DOCUMENTS_SUBMITTED"
  | "UNDER_VERIFICATION"
  | "VERIFIED"
  | "REJECTED"
  | "SUSPENDED";

export type TransporterAccountStatus = "ACTIVE" | "INACTIVE" | "SUSPENDED";

export type VehicleStatus = "ACTIVE" | "MAINTENANCE" | "EXPIRED_DOCUMENTS" | "INACTIVE";

export type DriverStatus = "ACTIVE" | "ON_DUTY" | "OFF_DUTY" | "EXPIRED_LICENSE" | "SUSPENDED";

export interface TransporterDocumentItem {
  doc_type: string;
  document_number?: string | null;
  file_url: string;
  expiry_date?: string | null;
  submitted_at: string;
  status: string;
}

export interface ServiceAreaResponse {
  id: string;
  transporter_id: string;
  origin_region: string;
  destination_region: string;
  origin_postal_code_prefix?: string | null;
  destination_postal_code_prefix?: string | null;
  estimated_transit_hours: number;
  is_active: boolean;
  created_at: string;
}

export interface VehicleListItem {
  id: string;
  transporter_id: string;
  transporter_name: string;
  license_plate: string;
  vehicle_type: string;
  capacity_kg: number;
  volume_cbm?: number | null;
  is_available: boolean;
  status: VehicleStatus;
  has_expired_documents: boolean;
  insurance_expiry?: string | null;
  fitness_expiry?: string | null;
  rc_number?: string | null;
  telematics_device_id?: string | null;
  assigned_driver_id?: string | null;
  assigned_driver_name?: string | null;
  created_at: string;
}

export interface DriverListItem {
  id: string;
  transporter_id: string;
  transporter_name: string;
  first_name: string;
  last_name: string;
  full_name: string;
  phone: string;
  license_number: string;
  license_number_masked: string;
  license_expiry?: string | null;
  is_license_expired: boolean;
  is_available: boolean;
  status: DriverStatus;
  assigned_vehicle_id?: string | null;
  assigned_vehicle_plate?: string | null;
  created_at: string;
}

export interface TransporterPerformanceSummary {
  reliability_score: number;
  total_deliveries: number;
  on_time_deliveries: number;
  on_time_rate: number;
  active_exceptions: number;
  accepted_bookings_count: number;
  rejected_bookings_count: number;
  total_fleet_capacity_kg: number;
}

export interface TransporterBookingSummaryItem {
  id: string;
  shipment_id: string;
  shipment_tracking_number: string;
  origin_summary: string;
  destination_summary: string;
  status: string;
  offered_rate?: number | null;
  agreed_rate?: number | null;
  created_at: string;
}

export interface TransporterListItem {
  id: string;
  organization_id: string;
  name: string;
  code: string;
  contact_person?: string | null;
  phone: string;
  email?: string | null;
  gstin?: string | null;
  is_active: boolean;
  account_status: TransporterAccountStatus;
  verification_status: TransporterVerificationStatus;
  reliability_score: number;
  total_deliveries: number;
  on_time_deliveries: number;
  on_time_delivery_rate: number;
  total_vehicles: number;
  active_vehicles: number;
  total_drivers: number;
  active_drivers: number;
  service_regions: string[];
  vehicle_categories: string[];
  max_cargo_capacity_kg?: number | null;
  created_at: string;
}

export interface TransporterDetailResponse {
  id: string;
  organization_id: string;
  name: string;
  code: string;
  contact_person?: string | null;
  phone: string;
  email?: string | null;
  gstin?: string | null;
  is_active: boolean;
  account_status: TransporterAccountStatus;
  verification_status: TransporterVerificationStatus;
  verification_notes?: string | null;
  verified_at?: string | null;
  verified_by_user?: string | null;
  service_regions: string[];
  operating_routes: string[];
  vehicle_categories: string[];
  max_cargo_capacity_kg?: number | null;
  documents: TransporterDocumentItem[];
  vehicles: VehicleListItem[];
  drivers: DriverListItem[];
  service_areas: ServiceAreaResponse[];
  recent_bookings: TransporterBookingSummaryItem[];
  performance: TransporterPerformanceSummary;
  created_at: string;
  updated_at: string;
}

export interface PaginatedTransportersResponse {
  items: TransporterListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PaginatedVehiclesResponse {
  items: VehicleListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PaginatedDriversResponse {
  items: DriverListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface TransporterCreatePayload {
  name: string;
  code?: string;
  contact_person?: string;
  phone: string;
  email?: string;
  gstin?: string;
  service_regions?: string[];
  operating_routes?: string[];
  vehicle_categories?: string[];
  max_cargo_capacity_kg?: number;
}

export interface TransporterUpdatePayload {
  name?: string;
  contact_person?: string;
  phone?: string;
  email?: string;
  gstin?: string;
  service_regions?: string[];
  operating_routes?: string[];
  vehicle_categories?: string[];
  max_cargo_capacity_kg?: number;
  is_active?: boolean;
}

export interface TransporterVerificationPayload {
  status: TransporterVerificationStatus;
  verification_notes?: string;
}

export interface DocumentUploadPayload {
  doc_type: string;
  document_number?: string;
  file_url: string;
  expiry_date?: string;
}

export interface ServiceAreaCreatePayload {
  origin_region: string;
  destination_region: string;
  origin_postal_code_prefix?: string;
  destination_postal_code_prefix?: string;
  estimated_transit_hours?: number;
}

export interface VehicleCreatePayload {
  transporter_id: string;
  license_plate: string;
  vehicle_type: string;
  capacity_kg: number;
  volume_cbm?: number;
  rc_number?: string;
  insurance_expiry?: string;
  fitness_expiry?: string;
  telematics_device_id?: string;
  is_available?: boolean;
}

export interface VehicleUpdatePayload {
  vehicle_type?: string;
  capacity_kg?: number;
  volume_cbm?: number;
  rc_number?: string;
  insurance_expiry?: string;
  fitness_expiry?: string;
  telematics_device_id?: string;
  is_available?: boolean;
}

export interface DriverCreatePayload {
  transporter_id: string;
  first_name: string;
  last_name: string;
  phone: string;
  license_number: string;
  license_expiry?: string;
  is_available?: boolean;
  assigned_vehicle_id?: string;
}

export interface DriverUpdatePayload {
  first_name?: string;
  last_name?: string;
  phone?: string;
  license_number?: string;
  license_expiry?: string;
  is_available?: boolean;
  assigned_vehicle_id?: string;
}

// ============================================================================
// API Client Functions
// ============================================================================

export async function listTransporters(params?: {
  page?: number;
  page_size?: number;
  search?: string;
  verification_status?: string;
  is_active?: boolean;
}): Promise<PaginatedTransportersResponse> {
  const query = new URLSearchParams();
  if (params?.page) query.set("page", params.page.toString());
  if (params?.page_size) query.set("page_size", params.page_size.toString());
  if (params?.search) query.set("search", params.search);
  if (params?.verification_status) query.set("verification_status", params.verification_status);
  if (params?.is_active !== undefined) query.set("is_active", params.is_active.toString());

  const response = await apiClient.get<PaginatedTransportersResponse>(`/transporters?${query.toString()}`);
  return response as any;
}

export async function getTransporter(id: string): Promise<TransporterDetailResponse> {
  const response = await apiClient.get<TransporterDetailResponse>(`/transporters/${id}`);
  return response as any;
}

export async function createTransporter(data: TransporterCreatePayload): Promise<TransporterListItem> {
  const response = await apiClient.post<TransporterListItem>("/transporters", data);
  return response as any;
}

export async function updateTransporter(id: string, data: TransporterUpdatePayload): Promise<TransporterDetailResponse> {
  const response = await apiClient.put<TransporterDetailResponse>(`/transporters/${id}`, data);
  return response as any;
}

export async function verifyTransporter(
  id: string,
  payload: TransporterVerificationPayload
): Promise<TransporterDetailResponse> {
  const response = await apiClient.post<TransporterDetailResponse>(`/transporters/${id}/verify`, payload);
  return response as any;
}

export async function suspendTransporter(id: string, reason: string): Promise<TransporterDetailResponse> {
  const query = new URLSearchParams({ reason });
  const response = await apiClient.post<TransporterDetailResponse>(`/transporters/${id}/suspend?${query.toString()}`);
  return response as any;
}

export async function uploadTransporterDocument(
  id: string,
  data: DocumentUploadPayload
): Promise<TransporterDetailResponse> {
  const response = await apiClient.post<TransporterDetailResponse>(`/transporters/${id}/documents`, data);
  return response as any;
}

export async function addTransporterServiceArea(
  id: string,
  data: ServiceAreaCreatePayload
): Promise<ServiceAreaResponse> {
  const response = await apiClient.post<ServiceAreaResponse>(`/transporters/${id}/service-areas`, data);
  return response as any;
}

// Vehicles
export async function listVehicles(params?: {
  page?: number;
  page_size?: number;
  transporter_id?: string;
  vehicle_type?: string;
  is_available?: boolean;
  has_expired_documents?: boolean;
  search?: string;
}): Promise<PaginatedVehiclesResponse> {
  const query = new URLSearchParams();
  if (params?.page) query.set("page", params.page.toString());
  if (params?.page_size) query.set("page_size", params.page_size.toString());
  if (params?.transporter_id) query.set("transporter_id", params.transporter_id);
  if (params?.vehicle_type) query.set("vehicle_type", params.vehicle_type);
  if (params?.is_available !== undefined) query.set("is_available", params.is_available.toString());
  if (params?.has_expired_documents !== undefined) query.set("has_expired_documents", params.has_expired_documents.toString());
  if (params?.search) query.set("search", params.search);

  const response = await apiClient.get<PaginatedVehiclesResponse>(`/vehicles?${query.toString()}`);
  return response as any;
}

export async function createVehicle(data: VehicleCreatePayload): Promise<VehicleListItem> {
  const response = await apiClient.post<VehicleListItem>("/vehicles", data);
  return response as any;
}

export async function updateVehicle(id: string, data: VehicleUpdatePayload): Promise<VehicleListItem> {
  const response = await apiClient.put<VehicleListItem>(`/vehicles/${id}`, data);
  return response as any;
}

export async function deleteVehicle(id: string): Promise<{ success: boolean; message: string }> {
  const response = await apiClient.delete<{ success: boolean; message: string }>(`/vehicles/${id}`);
  return response as any;
}

// Drivers
export async function listDrivers(params?: {
  page?: number;
  page_size?: number;
  transporter_id?: string;
  is_available?: boolean;
  is_license_expired?: boolean;
  search?: string;
}): Promise<PaginatedDriversResponse> {
  const query = new URLSearchParams();
  if (params?.page) query.set("page", params.page.toString());
  if (params?.page_size) query.set("page_size", params.page_size.toString());
  if (params?.transporter_id) query.set("transporter_id", params.transporter_id);
  if (params?.is_available !== undefined) query.set("is_available", params.is_available.toString());
  if (params?.is_license_expired !== undefined) query.set("is_license_expired", params.is_license_expired.toString());
  if (params?.search) query.set("search", params.search);

  const response = await apiClient.get<PaginatedDriversResponse>(`/drivers?${query.toString()}`);
  return response as any;
}

export async function createDriver(data: DriverCreatePayload): Promise<DriverListItem> {
  const response = await apiClient.post<DriverListItem>("/drivers", data);
  return response as any;
}

export async function updateDriver(id: string, data: DriverUpdatePayload): Promise<DriverListItem> {
  const response = await apiClient.put<DriverListItem>(`/drivers/${id}`, data);
  return response as any;
}

export async function assignDriverToVehicle(driverId: string, vehicleId: string | null): Promise<DriverListItem> {
  const response = await apiClient.post<DriverListItem>(`/drivers/${driverId}/assign-vehicle`, {
    vehicle_id: vehicleId,
  });
  return response as any;
}

export async function deleteDriver(id: string): Promise<{ success: boolean; message: string }> {
  const response = await apiClient.delete<{ success: boolean; message: string }>(`/drivers/${id}`);
  return response as any;
}
