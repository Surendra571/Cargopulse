import { apiClient } from "@/lib/api-client";

// ============================================================================
// Enums & Types
// ============================================================================

export type ShipmentMilestone =
  | "SHIPMENT_CREATED"
  | "TRANSPORTER_ASSIGNED"
  | "BOOKING_CONFIRMED"
  | "VEHICLE_ASSIGNED"
  | "VEHICLE_ARRIVED"
  | "PICKUP_COMPLETED"
  | "IN_TRANSIT"
  | "CHECKPOINT_REACHED"
  | "OUT_FOR_DELIVERY"
  | "DELIVERED";

export type TrackingEventSource =
  | "TRANSPORTER"
  | "DRIVER"
  | "OPERATOR"
  | "WEBHOOK"
  | "SYSTEM"
  | "TELEMATICS"
  | "DRIVER_APP"
  | "USER";

export interface TrackingEvent {
  id: string;
  organization_id: string;
  shipment_id: string;
  event_type: string;
  milestone?: string | null;
  description: string;
  occurred_at: string;
  latitude?: number | null;
  longitude?: number | null;
  location_name?: string | null;
  source: string;
  idempotency_key?: string | null;
  estimated_delivery_at?: string | null;
  created_by_user_id?: string | null;
  payload?: Record<string, any>;
}

export interface MilestoneProgressItem {
  milestone: string;
  label: string;
  completed: boolean;
  occurred_at?: string | null;
  location_name?: string | null;
  is_current: boolean;
}

export interface LocationSummary {
  name: string;
  city: string;
  state: string;
  postal_code: string;
  dock_number?: string | null;
  contact_name: string;
  contact_phone: string;
}

export interface ShipmentTimelineResponse {
  shipment_id: string;
  tracking_number: string;
  status: string;
  current_milestone?: string | null;
  scheduled_pickup_time: string;
  actual_pickup_time?: string | null;
  expected_delivery_time: string;
  actual_delivery_time?: string | null;
  is_tracking_stale: boolean;
  last_tracking_event_at?: string | null;
  last_known_location?: string | null;
  last_known_latitude?: number | null;
  last_known_longitude?: number | null;
  eta_delay_minutes: number;
  total_weight_kg: number;
  goods_description: string;
  origin: LocationSummary;
  destination: LocationSummary;
  transporter?: {
    id: string;
    name: string;
    code: string;
    phone?: string;
  } | null;
  assigned_vehicle?: {
    id?: string;
    license_plate: string;
    vehicle_type?: string;
  } | null;
  assigned_driver?: {
    id?: string;
    name: string;
    phone?: string;
  } | null;
  events: TrackingEvent[];
  milestone_progress: MilestoneProgressItem[];
}

export interface TrackedShipmentItem {
  id: string;
  tracking_number: string;
  status: string;
  current_milestone?: string | null;
  origin_city: string;
  destination_city: string;
  expected_delivery_time: string;
  actual_delivery_time?: string | null;
  last_known_location?: string | null;
  last_known_latitude?: number | null;
  last_known_longitude?: number | null;
  last_tracking_event_at?: string | null;
  is_tracking_stale: boolean;
  eta_delay_minutes: number;
  total_weight_kg: number;
  carrier?: { id: string; name: string } | null;
  vehicle?: { license_plate: string } | null;
  driver?: { name: string } | null;
}

export interface TrackedShipmentListResponse {
  items: TrackedShipmentItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface TrackingScanResponse {
  scanned_count: number;
  stale_flagged_count: number;
  exceptions_created: number;
  simulated_now: string;
}

// ============================================================================
// API Methods
// ============================================================================

export const trackingApi = {
  listTrackedShipments: async (params?: {
    page?: number;
    page_size?: number;
    status?: string;
    is_stale?: boolean;
    current_milestone?: string;
    search?: string;
  }): Promise<TrackedShipmentListResponse> => {
    const res = await apiClient.get<TrackedShipmentListResponse>("/tracking/shipments", {
      params,
    });
    return res as any;
  },

  getTimeline: async (shipmentId: string): Promise<ShipmentTimelineResponse> => {
    const res = await apiClient.get<ShipmentTimelineResponse>(
      `/tracking/shipments/${shipmentId}/timeline`
    );
    return res as any;
  },

  recordEvent: async (
    shipmentId: string,
    data: {
      milestone?: ShipmentMilestone;
      event_type?: string;
      description?: string;
      occurred_at?: string;
      latitude?: number;
      longitude?: number;
      location_name?: string;
      source?: TrackingEventSource;
      estimated_delivery_at?: string;
      idempotency_key?: string;
      payload?: Record<string, any>;
    }
  ): Promise<TrackingEvent> => {
    const res = await apiClient.post<TrackingEvent>(
      `/tracking/shipments/${shipmentId}/events`,
      data
    );
    return res as any;
  },

  updateETA: async (
    shipmentId: string,
    data: {
      new_eta: string;
      reason?: string;
      location_name?: string;
      latitude?: number;
      longitude?: number;
      source?: TrackingEventSource;
    }
  ): Promise<TrackingEvent> => {
    const res = await apiClient.post<TrackingEvent>(
      `/tracking/shipments/${shipmentId}/eta`,
      data
    );
    return res as any;
  },

  scanStaleTracking: async (params?: {
    threshold_hours?: number;
    simulated_now?: string;
  }): Promise<TrackingScanResponse> => {
    const res = await apiClient.post<TrackingScanResponse>(
      "/tracking/scan",
      {},
      { params }
    );
    return res as any;
  },

  getWebSocketUrl: (shipmentId?: string): string => {
    const base = apiClient.defaults.baseURL || "http://localhost:8000/api/v1";
    const wsBase = base.replace(/^http/, "ws");
    const token = localStorage.getItem("access_token");
    const query = token ? `?token=${encodeURIComponent(token)}` : "";
    if (shipmentId) {
      return `${wsBase}/tracking/ws/${shipmentId}${query}`;
    }
    return `${wsBase}/tracking/ws${query}`;
  },
};
