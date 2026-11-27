import React, { useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Truck,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ShieldCheck,
  Scale,
  DollarSign,
  Calendar,
  MapPin,
  Clock,
  Sliders,
  ChevronDown,
  ChevronUp,
  Sparkles,
  ArrowRight,
  ExternalLink,
  BadgeAlert,
} from "lucide-react";

import { matchingApi, TransporterRecommendationItem, TransporterSelectionRequest } from "@/api/matching";
import { shipmentApi, ShipmentListItem } from "@/api/shipments";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

export const MatchingPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const currentShipmentId = searchParams.get("shipment_id") || "";

  // Selection modal state
  const [selectedCarrier, setSelectedCarrier] = useState<TransporterRecommendationItem | null>(null);
  const [selectedVehicleId, setSelectedVehicleId] = useState<string>("");
  const [agreedRate, setAgreedRate] = useState<string>("");
  const [bookingNotes, setBookingNotes] = useState<string>("");
  const [isExcludedExpanded, setIsExcludedExpanded] = useState<boolean>(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // 1. Fetch eligible shipments to select if none chosen
  const { data: shipmentsData } = useQuery({
    queryKey: ["eligible_shipments_for_match"],
    queryFn: () => shipmentApi.listShipments({ page_size: 50 }),
  });

  // 2. Fetch matching recommendations for selected shipment
  const {
    data: matchData,
    isLoading: isLoadingMatch,
    isError: isMatchError,
    error: matchError,
    refetch: refetchMatch,
  } = useQuery({
    queryKey: ["matching_recommendations", currentShipmentId],
    queryFn: () => matchingApi.getRecommendations(currentShipmentId),
    enabled: !!currentShipmentId,
  });

  // 3. Selection mutation
  const selectCarrierMutation = useMutation({
    mutationFn: (payload: TransporterSelectionRequest) =>
      matchingApi.selectTransporter(currentShipmentId, payload),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["matching_recommendations", currentShipmentId] });
      queryClient.invalidateQueries({ queryKey: ["shipment", currentShipmentId] });
      queryClient.invalidateQueries({ queryKey: ["shipments"] });
      setSelectedCarrier(null);
      setSuccessMessage(
        `Carrier ${res.transporter_name} successfully booked for shipment ${res.tracking_number}!`
      );
      setTimeout(() => {
        navigate(`/shipments/${currentShipmentId}`);
      }, 1500);
    },
  });

  const handleOpenSelectModal = (carrier: TransporterRecommendationItem) => {
    setSelectedCarrier(carrier);
    if (carrier.eligible_vehicles.length > 0) {
      setSelectedVehicleId(carrier.eligible_vehicles[0].id);
    } else {
      setSelectedVehicleId("");
    }
    setAgreedRate(carrier.estimated_cost ? carrier.estimated_cost.toString() : "");
    setBookingNotes("");
  };

  const handleConfirmSelection = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCarrier || !currentShipmentId) return;

    const rateNum = agreedRate ? parseFloat(agreedRate) : undefined;
    selectCarrierMutation.mutate({
      transporter_id: selectedCarrier.transporter_id,
      vehicle_id: selectedVehicleId || undefined,
      agreed_rate: rateNum,
      booking_notes: bookingNotes || undefined,
    });
  };

  const candidateShipments = ((shipmentsData?.items || []) as ShipmentListItem[]).filter(
    (s: ShipmentListItem) => s.status === "DRAFT" || s.status === "PENDING_ACCEPTANCE"
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12 animate-in fade-in duration-200">
      <PageHeader
        title="Intelligent Transporter Matching"
        subtitle="Algorithmic scoring, hard compliance filtering, and dispatch recommendations."
        breadcrumbs={[
          { label: "Dashboard", href: "/overview" },
          { label: "Matching", href: "/matching" },
          ...(matchData ? [{ label: matchData.tracking_number, href: `/shipments/${matchData.shipment_id}` }] : []),
        ]}
      />

      {/* Success Notification Banner */}
      {successMessage && (
        <div className="p-4 rounded-xl bg-success-container border border-emerald-200 text-emerald-800 flex items-center gap-3">
          <CheckCircle2 className="h-5 w-5 text-success shrink-0" />
          <div className="text-sm font-medium">{successMessage}</div>
        </div>
      )}

      {/* Algorithmic Compliance & Legal Disclaimer Banner */}
      <div className="p-4 rounded-xl bg-surface-card text-on-surface flex flex-col md:flex-row items-start md:items-center justify-between gap-3 shadow-sm border border-outline-variant">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-indigo-500/20 text-indigo-400">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-indigo-300">
              Explainable Deterministic Engine
            </div>
            <div className="text-xs text-on-surface-muted mt-0.5">
              Recommendations are evaluated through strict hard filters (verification, capacity, corridor) and weighted historical reliability. Past performance does not guarantee future operational execution.
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Badge className="bg-surface-container text-on-surface-muted border-outline-strong text-[11px] font-mono px-2.5 py-1">
            Human-in-the-Loop Dispatch
          </Badge>
        </div>
      </div>

      {/* Shipment Target Bar */}
      <Card className="p-5 border-outline-variant bg-surface-card shadow-xs">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-primary-container text-primary rounded-xl">
              <Truck className="h-5 w-5" />
            </div>
            <div>
              <div className="text-xs text-on-surface-muted font-medium">Target Shipment</div>
              {matchData ? (
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-base font-bold text-on-surface font-mono">
                    {matchData.tracking_number}
                  </span>
                  <Link
                    to={`/shipments/${matchData.shipment_id}`}
                    className="text-xs text-primary hover:underline inline-flex items-center gap-0.5"
                  >
                    View Details <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>
              ) : (
                <div className="text-sm text-on-surface-muted font-medium mt-0.5">
                  Select a shipment to evaluate carrier fit
                </div>
              )}
            </div>
          </div>

          {/* Quick Shipment Switcher */}
          <div className="flex items-center gap-2 self-start lg:self-auto">
            <select
              value={currentShipmentId}
              onChange={(e) => setSearchParams({ shipment_id: e.target.value })}
              className="text-xs bg-surface-container-low border border-outline-strong rounded-lg px-3 py-2 text-on-surface focus:outline-hidden focus:ring-2 focus:ring-burnt-orange min-w-[280px]"
            >
              <option value="">-- Choose Shipment to Match --</option>
              {candidateShipments.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.tracking_number} ({s.origin_city} &rarr; {s.destination_city} • {s.total_weight_kg.toLocaleString()} kg)
                </option>
              ))}
            </select>
            {currentShipmentId && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => refetchMatch()}
                className="h-8 text-xs text-on-surface-muted"
              >
                Re-evaluate
              </Button>
            )}
          </div>
        </div>

        {/* Selected Shipment Specs Strip */}
        {matchData && (
          <div className="mt-4 pt-4 border-t border-outline-variant grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            <div>
              <span className="text-on-surface-subtle block font-medium">Route Corridor</span>
              <span className="font-semibold text-on-surface flex items-center gap-1 mt-0.5">
                <MapPin className="h-3.5 w-3.5 text-primary" />
                {matchData.origin_city}, {matchData.origin_state} &rarr; {matchData.destination_city}, {matchData.destination_state}
              </span>
            </div>
            <div>
              <span className="text-on-surface-subtle block font-medium">Cargo Specifications</span>
              <span className="font-semibold text-on-surface flex items-center gap-1 mt-0.5">
                <Scale className="h-3.5 w-3.5 text-indigo-500" />
                {matchData.total_weight_kg.toLocaleString()} kg • {matchData.required_vehicle_type}
              </span>
            </div>
            <div>
              <span className="text-on-surface-subtle block font-medium">Pickup Deadline</span>
              <span className="font-semibold text-on-surface flex items-center gap-1 mt-0.5">
                <Clock className="h-3.5 w-3.5 text-amber-500" />
                {new Date(matchData.scheduled_pickup_time).toLocaleString()}
              </span>
            </div>
            <div>
              <span className="text-on-surface-subtle block font-medium">Delivery Deadline</span>
              <span className="font-semibold text-on-surface flex items-center gap-1 mt-0.5">
                <Calendar className="h-3.5 w-3.5 text-emerald-500" />
                {new Date(matchData.expected_delivery_time).toLocaleString()}
              </span>
            </div>
          </div>
        )}
      </Card>

      {/* Empty State when no shipment selected */}
      {!currentShipmentId && (
        <Card className="p-12 text-center bg-surface-card border-outline-variant">
          <Truck className="h-12 w-12 text-on-surface-muted mx-auto mb-3" />
          <h3 className="text-base font-semibold text-on-surface">Select a Target Shipment</h3>
          <p className="text-xs text-on-surface-muted max-w-md mx-auto mt-1 mb-6">
            Choose an unassigned or pending shipment from your dispatch board above to evaluate eligible carriers and run the scoring model.
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {candidateShipments.slice(0, 3).map((s) => (
              <Button
                key={s.id}
                variant="outline"
                size="sm"
                onClick={() => setSearchParams({ shipment_id: s.id })}
                className="text-xs"
              >
                Match {s.tracking_number} ({s.origin_city} &rarr; {s.destination_city})
              </Button>
            ))}
          </div>
        </Card>
      )}

      {/* Loading State */}
      {isLoadingMatch && (
        <div className="p-12 text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-3" />
          <div className="text-sm font-medium text-on-surface">Evaluating carrier network...</div>
          <div className="text-xs text-on-surface-subtle mt-1">Applying hard filters and calculating 5-component scorecard</div>
        </div>
      )}

      {/* Error State */}
      {isMatchError && (
        <Card className="p-6 bg-critical-container border-rose-200 text-rose-800">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-critical" />
            <h4 className="font-semibold text-sm">Failed to evaluate carrier matches</h4>
          </div>
          <p className="text-xs text-on-critical-container mt-1">
            {(matchError as any)?.response?.data?.detail || "An unexpected error occurred during matching."}
          </p>
        </Card>
      )}

      {/* Match Results View */}
      {matchData && (
        <div className="space-y-6">
          {/* Summary KPIs & Weights Inspector */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Card className="p-3.5 bg-surface-card border-outline-variant">
              <div className="text-[11px] font-medium text-on-surface-muted uppercase">Carriers Evaluated</div>
              <div className="text-xl font-bold text-on-surface mt-1 font-mono">
                {matchData.total_carriers_evaluated}
              </div>
              <div className="text-[10px] text-on-surface-subtle mt-0.5">Total registered in organization</div>
            </Card>

            <Card className="p-3.5 bg-success-container/50 border-emerald-200">
              <div className="text-[11px] font-medium text-on-success-container uppercase">Eligible Recommendations</div>
              <div className="text-xl font-bold text-emerald-900 mt-1 font-mono">
                {matchData.eligible_carriers_count}
              </div>
              <div className="text-[10px] text-success mt-0.5">Passed all Step 1 hard filters</div>
            </Card>

            <Card className="p-3.5 bg-critical-container/50 border-rose-200">
              <div className="text-[11px] font-medium text-on-critical-container uppercase">Excluded by Hard Filter</div>
              <div className="text-xl font-bold text-rose-900 mt-1 font-mono">
                {matchData.excluded_carriers_count}
              </div>
              <div className="text-[10px] text-critical mt-0.5">Unverified, capacity or corridor gap</div>
            </Card>

            <Card className="p-3.5 bg-primary-container/50 border-burnt-orange/30">
              <div className="text-[11px] font-medium text-primary uppercase">Top Match Score</div>
              <div className="text-xl font-bold text-blue-900 mt-1 font-mono">
                {matchData.recommendations.length > 0
                  ? `${matchData.recommendations[0].match_score}/100`
                  : "N/A"}
              </div>
              <div className="text-[10px] text-primary mt-0.5">
                {matchData.recommendations.length > 0
                  ? matchData.recommendations[0].transporter_name
                  : "No eligible matches"}
              </div>
            </Card>
          </div>

          {/* Configurable Weights Ribbon */}
          <div className="p-3.5 bg-surface-container-low rounded-xl border border-outline-variant flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2 text-on-surface font-semibold">
              <Sliders className="h-4 w-4 text-primary" />
              <span>Scoring Weights:</span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-2.5 py-1 rounded-md bg-surface-card border border-outline-variant text-on-surface font-mono">
                Pickup Reliability: <strong className="text-primary">40%</strong>
              </span>
              <span className="px-2.5 py-1 rounded-md bg-surface-card border border-outline-variant text-on-surface font-mono">
                On-Time Delivery: <strong className="text-primary">25%</strong>
              </span>
              <span className="px-2.5 py-1 rounded-md bg-surface-card border border-outline-variant text-on-surface font-mono">
                Booking Acceptance: <strong className="text-primary">15%</strong>
              </span>
              <span className="px-2.5 py-1 rounded-md bg-surface-card border border-outline-variant text-on-surface font-mono">
                Route Suitability: <strong className="text-primary">10%</strong>
              </span>
              <span className="px-2.5 py-1 rounded-md bg-surface-card border border-outline-variant text-on-surface font-mono">
                Cost Competitiveness: <strong className="text-primary">10%</strong>
              </span>
            </div>
          </div>

          {/* SECTION: RANKED RECOMMENDATIONS */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-on-surface uppercase tracking-wider flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-success" />
                Ranked Eligible Transporters ({matchData.recommendations.length})
              </h3>
              <span className="text-xs text-on-surface-muted">
                Sorted by explainable match score
              </span>
            </div>

            {matchData.recommendations.length === 0 ? (
              <Card className="p-8 text-center bg-surface-card border-outline-variant">
                <AlertTriangle className="h-10 w-10 text-amber-500 mx-auto mb-2" />
                <h4 className="text-sm font-semibold text-on-surface">No Eligible Transporters Found</h4>
                <p className="text-xs text-on-surface-muted max-w-md mx-auto mt-1">
                  None of the registered carriers passed all hard filters for this shipment's vehicle type, weight, or corridor. Check the excluded carriers below to inspect the causes.
                </p>
              </Card>
            ) : (
              <div className="space-y-4">
                {matchData.recommendations.map((carrier) => {
                  const isTopRank = carrier.rank === 1;

                  return (
                    <Card
                      key={carrier.transporter_id}
                      className={`p-5 transition-all bg-surface-card border ${
                        isTopRank
                          ? "border-emerald-300 ring-2 ring-emerald-100 shadow-sm"
                          : "border-outline-variant hover:border-outline-strong shadow-xs"
                      }`}
                    >
                      <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                        {/* Carrier Identifiers & Badges */}
                        <div className="flex-1 space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <span
                              className={`px-2.5 py-0.5 rounded-full text-xs font-bold font-mono ${
                                isTopRank
                                  ? "bg-emerald-600 text-white"
                                  : "bg-surface-container text-on-surface"
                              }`}
                            >
                              Rank #{carrier.rank}
                            </span>

                            <h4 className="text-base font-bold text-on-surface">
                              {carrier.transporter_name}
                            </h4>

                            <Badge className="bg-surface-container text-on-surface border-outline-variant text-[10px] font-mono">
                              {carrier.transporter_code}
                            </Badge>

                            <Badge className="bg-success-container text-on-success-container border-emerald-200 text-[10px] gap-1">
                              <ShieldCheck className="h-3 w-3" />
                              VERIFIED
                            </Badge>

                            {carrier.is_new_transporter && (
                              <Badge className="bg-warning-container text-on-warning-container border-amber-200 text-[10px]">
                                New Partner Baseline
                              </Badge>
                            )}

                            {carrier.route_suitability_type === "DIRECT_LANE" && (
                              <Badge className="bg-success-container text-on-success-container border-emerald-200 text-[10px]">
                                Direct Lane SLA
                              </Badge>
                            )}
                            {carrier.route_suitability_type === "OPERATING_CORRIDOR" && (
                              <Badge className="bg-primary-container text-primary border-burnt-orange/30 text-[10px]">
                                Operating Corridor
                              </Badge>
                            )}
                            {carrier.route_suitability_type === "REGIONAL_COVERAGE" && (
                              <Badge className="bg-purple-50 text-purple-700 border-purple-200 text-[10px]">
                                Regional Hub
                              </Badge>
                            )}
                          </div>

                          <p className="text-xs text-on-surface-muted">
                            {carrier.recommendation_summary}
                          </p>

                          {/* Fleet details */}
                          <div className="flex flex-wrap items-center gap-4 text-xs text-on-surface-muted pt-1">
                            <span>
                              Phone: <strong className="text-on-surface">{carrier.phone}</strong>
                            </span>
                            <span>•</span>
                            <span>
                              Eligible Vehicles:{" "}
                              <strong className="text-on-surface">
                                {carrier.total_eligible_vehicles_count} units
                              </strong>
                            </span>
                            <span>•</span>
                            <span>
                              Estimated Tariff:{" "}
                              <strong className="text-on-success-container font-mono">
                                {carrier.estimated_cost
                                  ? `$${carrier.estimated_cost.toFixed(2)} ${carrier.currency}`
                                  : "Quote Required"}
                              </strong>
                            </span>
                          </div>
                        </div>

                        {/* Overall Match Score & Selection Action */}
                        <div className="flex lg:flex-col items-center lg:items-end justify-between gap-3 shrink-0">
                          <div className="text-right">
                            <div className="text-2xl font-black text-on-surface font-mono tracking-tight">
                              {carrier.match_score.toFixed(1)}
                              <span className="text-xs font-medium text-on-surface-subtle">/100</span>
                            </div>
                            <div className="text-[10px] text-on-surface-subtle font-medium">Match Fit Score</div>
                          </div>

                          <Button
                            onClick={() => handleOpenSelectModal(carrier)}
                            size="sm"
                            className={`h-9 px-4 text-xs gap-1.5 font-semibold ${
                              isTopRank
                                ? "bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs"
                                : "bg-primary hover:bg-burnt-orange text-white"
                            }`}
                          >
                            Select & Book
                            <ArrowRight className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </div>

                      {/* Scorecard Breakdown 5-Meters */}
                      <div className="mt-4 pt-3 border-t border-outline-variant">
                        <div className="text-[11px] font-semibold text-on-surface-muted uppercase tracking-wider mb-2">
                          Explainable Scorecard Breakdown:
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-5 gap-2.5">
                          {/* 1. Pickup Reliability */}
                          <div className="p-2 rounded-lg bg-surface-container-low border border-outline-variant">
                            <div className="flex justify-between text-[11px] font-medium text-on-surface">
                              <span>Pickup (40%)</span>
                              <span className="font-mono font-bold text-on-surface">
                                {carrier.scorecard.pickup_reliability.score.toFixed(0)}%
                              </span>
                            </div>
                            <div className="w-full bg-surface-container h-1.5 rounded-full overflow-hidden mt-1">
                              <div
                                className="bg-primary h-full rounded-full"
                                style={{ width: `${carrier.scorecard.pickup_reliability.score}%` }}
                              />
                            </div>
                            <div className="text-[10px] text-on-surface-subtle truncate mt-1" title={carrier.scorecard.pickup_reliability.explanation}>
                              {carrier.scorecard.pickup_reliability.explanation}
                            </div>
                          </div>

                          {/* 2. On-Time Delivery */}
                          <div className="p-2 rounded-lg bg-surface-container-low border border-outline-variant">
                            <div className="flex justify-between text-[11px] font-medium text-on-surface">
                              <span>On-Time (25%)</span>
                              <span className="font-mono font-bold text-on-surface">
                                {carrier.scorecard.ontime_delivery.score.toFixed(0)}%
                              </span>
                            </div>
                            <div className="w-full bg-surface-container h-1.5 rounded-full overflow-hidden mt-1">
                              <div
                                className="bg-emerald-600 h-full rounded-full"
                                style={{ width: `${carrier.scorecard.ontime_delivery.score}%` }}
                              />
                            </div>
                            <div className="text-[10px] text-on-surface-subtle truncate mt-1" title={carrier.scorecard.ontime_delivery.explanation}>
                              {carrier.scorecard.ontime_delivery.explanation}
                            </div>
                          </div>

                          {/* 3. Acceptance */}
                          <div className="p-2 rounded-lg bg-surface-container-low border border-outline-variant">
                            <div className="flex justify-between text-[11px] font-medium text-on-surface">
                              <span>Acceptance (15%)</span>
                              <span className="font-mono font-bold text-on-surface">
                                {carrier.scorecard.booking_acceptance.score.toFixed(0)}%
                              </span>
                            </div>
                            <div className="w-full bg-surface-container h-1.5 rounded-full overflow-hidden mt-1">
                              <div
                                className="bg-indigo-600 h-full rounded-full"
                                style={{ width: `${carrier.scorecard.booking_acceptance.score}%` }}
                              />
                            </div>
                            <div className="text-[10px] text-on-surface-subtle truncate mt-1" title={carrier.scorecard.booking_acceptance.explanation}>
                              {carrier.scorecard.booking_acceptance.explanation}
                            </div>
                          </div>

                          {/* 4. Route */}
                          <div className="p-2 rounded-lg bg-surface-container-low border border-outline-variant">
                            <div className="flex justify-between text-[11px] font-medium text-on-surface">
                              <span>Route Fit (10%)</span>
                              <span className="font-mono font-bold text-on-surface">
                                {carrier.scorecard.route_suitability.score.toFixed(0)}%
                              </span>
                            </div>
                            <div className="w-full bg-surface-container h-1.5 rounded-full overflow-hidden mt-1">
                              <div
                                className="bg-teal-600 h-full rounded-full"
                                style={{ width: `${carrier.scorecard.route_suitability.score}%` }}
                              />
                            </div>
                            <div className="text-[10px] text-on-surface-subtle truncate mt-1" title={carrier.scorecard.route_suitability.explanation}>
                              {carrier.scorecard.route_suitability.explanation}
                            </div>
                          </div>

                          {/* 5. Cost */}
                          <div className="p-2 rounded-lg bg-surface-container-low border border-outline-variant">
                            <div className="flex justify-between text-[11px] font-medium text-on-surface">
                              <span>Cost Fit (10%)</span>
                              <span className="font-mono font-bold text-on-surface">
                                {carrier.scorecard.cost_competitiveness.score.toFixed(0)}%
                              </span>
                            </div>
                            <div className="w-full bg-surface-container h-1.5 rounded-full overflow-hidden mt-1">
                              <div
                                className="bg-purple-600 h-full rounded-full"
                                style={{ width: `${carrier.scorecard.cost_competitiveness.score}%` }}
                              />
                            </div>
                            <div className="text-[10px] text-on-surface-subtle truncate mt-1" title={carrier.scorecard.cost_competitiveness.explanation}>
                              {carrier.scorecard.cost_competitiveness.explanation}
                            </div>
                          </div>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            )}
          </div>

          {/* SECTION: EXCLUDED TRANSPORTERS DRAWER */}
          {matchData.excluded.length > 0 && (
            <Card className="border-outline-variant bg-surface-card overflow-hidden shadow-xs">
              <button
                type="button"
                onClick={() => setIsExcludedExpanded(!isExcludedExpanded)}
                className="w-full p-4 flex items-center justify-between bg-surface-container-low hover:bg-surface-container/80 transition-colors text-left"
              >
                <div className="flex items-center gap-2">
                  <XCircle className="h-4 w-4 text-rose-500" />
                  <span className="text-xs font-bold text-on-surface uppercase tracking-wider">
                    Disqualified Carriers ({matchData.excluded.length})
                  </span>
                  <span className="text-xs text-on-surface-muted">
                    — Excluded by Step 1 Hard Eligibility Filters
                  </span>
                </div>
                {isExcludedExpanded ? (
                  <ChevronUp className="h-4 w-4 text-on-surface-muted" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-on-surface-muted" />
                )}
              </button>

              {isExcludedExpanded && (
                <div className="p-4 divide-y divide-outline-variant space-y-3">
                  {matchData.excluded.map((carrier) => (
                    <div
                      key={carrier.transporter_id}
                      className="pt-3 first:pt-0 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-on-surface">{carrier.transporter_name}</span>
                          <span className="font-mono text-on-surface-subtle text-[11px]">({carrier.transporter_code})</span>
                          <Badge
                            className={`text-[10px] ${
                              carrier.verification_status === "VERIFIED"
                                ? "bg-success-container text-on-success-container"
                                : "bg-critical-container text-on-critical-container border-rose-200"
                            }`}
                          >
                            {carrier.verification_status}
                          </Badge>
                          {carrier.account_status === "SUSPENDED" && (
                            <Badge className="bg-rose-100 text-rose-800 border-rose-300 text-[10px]">
                              SUSPENDED
                            </Badge>
                          )}
                        </div>

                        {/* Ineligibility Reasons */}
                        <div className="mt-1 flex flex-wrap gap-1.5">
                          {carrier.ineligibility_reasons.map((reason, idx) => (
                            <span
                              key={idx}
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm bg-critical-container border border-rose-200 text-on-critical-container text-[11px]"
                            >
                              <BadgeAlert className="h-3 w-3 shrink-0" />
                              {reason}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div className="text-on-surface-subtle text-[11px] shrink-0 font-mono">
                        {carrier.total_eligible_vehicles_count} eligible vehicles
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}
        </div>
      )}

      {/* MODAL: DISPATCH SELECTION & BOOKING */}
      {selectedCarrier && matchData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-secondary/40 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="relative w-full max-w-lg rounded-2xl border border-outline-variant bg-surface-card p-6 shadow-xl animate-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-outline-variant pb-3 mb-4">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-lg bg-primary-container text-primary">
                  <Truck className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-on-surface">
                    Book & Assign Carrier
                  </h3>
                  <div className="text-xs text-on-surface-muted">
                    Dispatch tender for shipment {matchData.tracking_number}
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedCarrier(null)}
                className="text-on-surface-subtle hover:text-on-surface-muted text-sm font-semibold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleConfirmSelection} className="space-y-4 text-xs">
              {/* Selected Carrier Card */}
              <div className="p-3 bg-surface-container-low rounded-xl border border-outline-variant space-y-1">
                <div className="text-on-surface-muted font-medium text-[11px]">Selected Transporter</div>
                <div className="flex items-center justify-between">
                  <div className="font-bold text-sm text-on-surface">
                    {selectedCarrier.transporter_name}
                  </div>
                  <Badge className="bg-emerald-600 text-white text-[11px] font-mono">
                    Match {selectedCarrier.match_score.toFixed(1)}/100
                  </Badge>
                </div>
                <div className="text-on-surface-muted">
                  {selectedCarrier.phone} • {selectedCarrier.transporter_code}
                </div>
              </div>

              {/* Vehicle Selection */}
              <div>
                <label className="block font-semibold text-on-surface mb-1">
                  Assign Vehicle from Eligible Fleet:
                </label>
                {selectedCarrier.eligible_vehicles.length > 0 ? (
                  <select
                    value={selectedVehicleId}
                    onChange={(e) => setSelectedVehicleId(e.target.value)}
                    className="w-full bg-surface-container-low border border-outline-strong rounded-lg p-2 text-on-surface text-xs focus:ring-2 focus:ring-burnt-orange"
                  >
                    {selectedCarrier.eligible_vehicles.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.license_plate} — {v.vehicle_type} ({v.capacity_kg.toLocaleString()} kg max)
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="p-2.5 rounded-lg bg-warning-container text-amber-800 border border-amber-200">
                    No specific vehicle pre-assigned. Carrier will designate unit upon tender acceptance.
                  </div>
                )}
              </div>

              {/* Agreed Freight Rate */}
              <div>
                <label className="block font-semibold text-on-surface mb-1">
                  Agreed Freight Rate ($ USD):
                </label>
                <div className="relative">
                  <DollarSign className="h-4 w-4 absolute left-3 top-2.5 text-on-surface-subtle" />
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="e.g. 1450.00"
                    value={agreedRate}
                    onChange={(e) => setAgreedRate(e.target.value)}
                    className="pl-8 text-xs font-mono"
                  />
                </div>
                <span className="text-[10px] text-on-surface-subtle mt-0.5 block">
                  Leave blank if rate is subject to dynamic contract tariff.
                </span>
              </div>

              {/* Dispatch Notes */}
              <div>
                <label className="block font-semibold text-on-surface mb-1">
                  Dispatch Booking Notes / Special Instructions:
                </label>
                <textarea
                  rows={3}
                  value={bookingNotes}
                  onChange={(e) => setBookingNotes(e.target.value)}
                  placeholder="e.g. Driver must arrive at Bay 4 with safety gear. Call receiving manager 30 mins prior to delivery."
                  className="w-full bg-surface-container-low border border-outline-strong rounded-lg p-2.5 text-on-surface text-xs focus:ring-2 focus:ring-burnt-orange"
                />
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-outline-variant">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedCarrier(null)}
                  disabled={selectCarrierMutation.isPending}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  className="bg-primary hover:bg-burnt-orange text-white font-semibold gap-1.5"
                  disabled={selectCarrierMutation.isPending}
                >
                  {selectCarrierMutation.isPending ? "Confirming Booking..." : "Confirm & Tender Booking"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
