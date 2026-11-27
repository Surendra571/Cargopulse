import { apiClient } from "@/lib/api-client";

// ============================================================================
// Types & Interfaces
// ============================================================================

export interface ScorecardComponent {
  score: number;
  weight: number;
  weighted_score: number;
  explanation: string;
}

export interface ScorecardBreakdown {
  pickup_reliability: ScorecardComponent;
  ontime_delivery: ScorecardComponent;
  booking_acceptance: ScorecardComponent;
  route_suitability: ScorecardComponent;
  cost_competitiveness: ScorecardComponent;
}

export interface MatchedVehicleItem {
  id: string;
  license_plate: string;
  vehicle_type: string;
  capacity_kg: number;
  volume_cbm?: number | null;
  is_available: boolean;
  insurance_expiry?: string | null;
  fitness_expiry?: string | null;
}

export interface TransporterRecommendationItem {
  transporter_id: string;
  transporter_name: string;
  transporter_code: string;
  phone: string;
  email?: string | null;
  gstin?: string | null;
  verification_status: string;
  account_status: string;
  reliability_score: number;

  match_score: number;
  rank: number;
  is_eligible: boolean;
  ineligibility_reasons: string[];

  scorecard: ScorecardBreakdown;
  recommendation_summary: string;
  is_new_transporter: boolean;

  eligible_vehicles: MatchedVehicleItem[];
  total_eligible_vehicles_count: number;
  route_suitability_type: "DIRECT_LANE" | "OPERATING_CORRIDOR" | "REGIONAL_COVERAGE" | "GENERAL" | "NO_COVERAGE" | string;
  estimated_cost?: number | null;
  currency: string;
}

export interface MatchingAuditRecordResponse {
  action_id: string;
  action_type: string;
  confidence_score: number;
  decision_summary: string;
  prompt_summary: string;
  requires_human_approval: boolean;
  created_at: string;
  approved_at?: string | null;
  approved_by_user_id?: string | null;
}

export interface TransporterMatchingResponse {
  shipment_id: string;
  tracking_number: string;
  origin_city: string;
  origin_state: string;
  destination_city: string;
  destination_state: string;
  total_weight_kg: number;
  required_vehicle_type: string;
  scheduled_pickup_time: string;
  expected_delivery_time: string;

  total_carriers_evaluated: number;
  eligible_carriers_count: number;
  excluded_carriers_count: number;

  recommendations: TransporterRecommendationItem[];
  excluded: TransporterRecommendationItem[];
  weights_used: Record<string, number>;
  audit_record?: MatchingAuditRecordResponse | null;
  disclaimer: string;
}

export interface TransporterSelectionRequest {
  transporter_id: string;
  vehicle_id?: string | null;
  driver_id?: string | null;
  agreed_rate?: number | null;
  booking_notes?: string | null;
}

export interface TransporterSelectionResponse {
  success: boolean;
  message: string;
  shipment_id: string;
  tracking_number: string;
  transporter_id: string;
  transporter_name: string;
  transporter_code: string;
  booking_id?: string | null;
  assignment_id?: string | null;
  shipment_status: string;
  agreed_rate?: number | null;
  audit_log_id: string;
  selected_at: string;
}

// ============================================================================
// API Client Functions
// ============================================================================

export const matchingApi = {
  getRecommendations: async (shipmentId: string): Promise<TransporterMatchingResponse> => {
    const response = await apiClient.get<TransporterMatchingResponse>(
      `/shipments/${shipmentId}/match`
    );
    return response as any;
  },

  selectTransporter: async (
    shipmentId: string,
    payload: TransporterSelectionRequest
  ): Promise<TransporterSelectionResponse> => {
    const response = await apiClient.post<TransporterSelectionResponse>(
      `/shipments/${shipmentId}/match/select`,
      payload
    );
    return response as any;
  },
};
