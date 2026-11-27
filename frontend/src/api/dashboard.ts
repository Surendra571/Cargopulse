import { apiClient } from "@/lib/api-client";

export interface DashboardMetrics {
  total_shipments: number;
  pending_pickups: number;
  confirmed_bookings: number;
  pickups_at_risk: number;
  failed_pickups: number;
  in_transit_shipments: number;
  delayed_deliveries: number;
  delivered_shipments: number;
  open_exceptions: number;
  pickup_success_rate: number;
  on_time_delivery_rate: number;
}

export interface VolumeOverTimePoint {
  date: string;
  total_shipments: number;
  delivered: number;
  exceptions: number;
}

export interface PickupPerformanceBreakdown {
  total_commitments: number;
  on_time: number;
  delayed: number;
  failed: number;
  success_rate: number;
}

export interface DeliveryPerformanceBreakdown {
  total_deliveries: number;
  on_time: number;
  delayed: number;
  on_time_rate: number;
}

export interface TransporterReliabilityItem {
  transporter_id: string;
  transporter_name: string;
  transporter_code: string;
  total_shipments: number;
  on_time_pickups: number;
  on_time_deliveries: number;
  reliability_score: number;
  active_exceptions: number;
}

export interface ExceptionDistributionItem {
  category: string;
  count: number;
  percentage: number;
}

export interface RecentActivityItem {
  id: string;
  shipment_id: string;
  tracking_number: string;
  event_type: string;
  description: string;
  occurred_at: string;
  location_name?: string | null;
  source: string;
}

export interface DashboardOverviewResponse {
  metrics: DashboardMetrics;
  volume_over_time: VolumeOverTimePoint[];
  pickup_performance: PickupPerformanceBreakdown;
  delivery_performance: DeliveryPerformanceBreakdown;
  transporter_rankings: TransporterReliabilityItem[];
  exceptions_by_type: ExceptionDistributionItem[];
  exceptions_by_severity: ExceptionDistributionItem[];
  recent_activity: RecentActivityItem[];
}

export interface DashboardShipmentItem {
  id: string;
  tracking_number: string;
  status: string;
  origin_city: string;
  origin_state: string;
  destination_city: string;
  destination_state: string;
  transporter_id?: string | null;
  transporter_name?: string | null;
  scheduled_pickup_time: string;
  expected_delivery_time: string;
  actual_pickup_time?: string | null;
  actual_delivery_time?: string | null;
  total_weight_kg: number;
  package_count: number;
  is_at_risk: boolean;
  open_exceptions_count: number;
  created_at: string;
}

export interface DashboardExceptionItem {
  id: string;
  shipment_id: string;
  tracking_number: string;
  exception_type: string;
  severity: string;
  status: string;
  title: string;
  description: string;
  reported_at: string;
  transporter_name?: string | null;
}

export interface PaginatedShipmentsResponse {
  items: DashboardShipmentItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PaginatedExceptionsResponse {
  items: DashboardExceptionItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ShipmentEventItem {
  id: string;
  event_type: string;
  description: string;
  occurred_at: string;
  location_name?: string | null;
  source: string;
  latitude?: number | null;
  longitude?: number | null;
}

export interface ShipmentDetailResponse {
  id: string;
  tracking_number: string;
  status: string;
  origin_name: string;
  origin_address: string;
  origin_city: string;
  origin_state: string;
  origin_contact_name: string;
  origin_contact_phone: string;
  destination_name: string;
  destination_address: string;
  destination_city: string;
  destination_state: string;
  destination_contact_name: string;
  destination_contact_phone: string;
  scheduled_pickup_time: string;
  actual_pickup_time?: string | null;
  expected_delivery_time: string;
  actual_delivery_time?: string | null;
  total_weight_kg: number;
  package_count: number;
  goods_description: string;
  is_hazardous: boolean;
  transporter_id?: string | null;
  transporter_name?: string | null;
  driver_name?: string | null;
  vehicle_plate?: string | null;
  events: ShipmentEventItem[];
  exceptions: DashboardExceptionItem[];
  pod_verified: boolean;
  pod_signatory_name?: string | null;
  pod_verified_at?: string | null;
  created_at: string;
}

export interface DashboardFilterParams {
  start_date?: string;
  end_date?: string;
  transporter_id?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

export const dashboardApi = {
  getOverview: async (params?: DashboardFilterParams): Promise<DashboardOverviewResponse> => {
    const res = await apiClient.get<DashboardOverviewResponse>("/api/v1/dashboard/overview", {
      params,
    });
    return res as any;
  },

  getMetrics: async (params?: DashboardFilterParams): Promise<DashboardMetrics> => {
    const res = await apiClient.get<DashboardMetrics>("/api/v1/dashboard/metrics", {
      params,
    });
    return res as any;
  },

  getVolumeChart: async (params?: DashboardFilterParams): Promise<VolumeOverTimePoint[]> => {
    const res = await apiClient.get<VolumeOverTimePoint[]>("/api/v1/dashboard/charts/volume", {
      params,
    });
    return res as any;
  },

  getTransporterRankings: async (params?: DashboardFilterParams): Promise<TransporterReliabilityItem[]> => {
    const res = await apiClient.get<TransporterReliabilityItem[]>("/api/v1/dashboard/charts/transporters", {
      params,
    });
    return res as any;
  },

  getTableAttention: async (params?: DashboardFilterParams): Promise<PaginatedShipmentsResponse> => {
    const res = await apiClient.get<PaginatedShipmentsResponse>("/api/v1/dashboard/tables/attention", {
      params,
    });
    return res as any;
  },

  getTableUpcomingPickups: async (params?: DashboardFilterParams): Promise<PaginatedShipmentsResponse> => {
    const res = await apiClient.get<PaginatedShipmentsResponse>("/api/v1/dashboard/tables/upcoming-pickups", {
      params,
    });
    return res as any;
  },

  getTableFailedPickups: async (params?: DashboardFilterParams): Promise<PaginatedShipmentsResponse> => {
    const res = await apiClient.get<PaginatedShipmentsResponse>("/api/v1/dashboard/tables/failed-pickups", {
      params,
    });
    return res as any;
  },

  getTableDeliveries: async (params?: DashboardFilterParams): Promise<PaginatedShipmentsResponse> => {
    const res = await apiClient.get<PaginatedShipmentsResponse>("/api/v1/dashboard/tables/deliveries", {
      params,
    });
    return res as any;
  },

  getTableExceptions: async (params?: DashboardFilterParams): Promise<PaginatedExceptionsResponse> => {
    const res = await apiClient.get<PaginatedExceptionsResponse>("/api/v1/dashboard/tables/exceptions", {
      params,
    });
    return res as any;
  },

  getShipmentDetail: async (shipmentId: string): Promise<ShipmentDetailResponse> => {
    const res = await apiClient.get<ShipmentDetailResponse>(`/api/v1/dashboard/shipments/${shipmentId}`);
    return res as any;
  },
};

