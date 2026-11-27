import React, { useState, useMemo } from "react";
import { useLocation } from "react-router-dom";
import { PageHeader } from "@/components/common/PageHeader";
import { MetricCard } from "@/components/common/MetricCard";
import { SearchBar } from "@/components/common/SearchBar";
import { DataTable, ColumnDef } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/context/ToastContext";
import {
  Package,
  Truck,
  Car,
  Users2,
  Sparkles,
  CalendarDays,
  Radio,
  MapPin,
  AlertTriangle,
  Bot,
  FileCheck2,
  Receipt,
  BarChart3,
  Cable,
  ShieldCheck,
  Plus,
  RefreshCw,
} from "lucide-react";

interface MetricItem {
  title: string;
  value: string | number;
  change?: number;
  trend?: "up" | "down" | "neutral";
  period?: string;
}

interface ModuleConfig {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  primaryActionLabel: string;
  metric1: MetricItem;
  metric2: MetricItem;
  metric3: MetricItem;
  metric4: MetricItem;
  dataColumns: ColumnDef<any>[];
  dataRows: any[];
}

const MODULE_REGISTRY: Record<string, ModuleConfig> = {
  shipments: {
    title: "Shipment Management",
    subtitle: "Create, monitor, and dispatch outbound manufacturing freight consignments.",
    icon: <Package className="h-5 w-5" />,
    primaryActionLabel: "New Shipment",
    metric1: { title: "Active Shipments", value: "142", change: 8.4, trend: "up", period: "vs last week" },
    metric2: { title: "Pending Dispatch", value: "18", change: -2.1, trend: "down", period: "within 4 hours" },
    metric3: { title: "In Transit", value: "89", change: 5.0, trend: "up", period: "on schedule" },
    metric4: { title: "Delivery SLA", value: "99.1%", change: 0.3, trend: "up", period: "last 30 days" },
    dataColumns: [
      { id: "ref", header: "Shipment Ref", cell: (r: any) => <span className="font-semibold text-blue-600">{r.ref}</span> },
      { id: "origin", header: "Origin", cell: (r: any) => <span>{r.origin}</span> },
      { id: "destination", header: "Destination", cell: (r: any) => <span>{r.destination}</span> },
      { id: "transporter", header: "Transporter", cell: (r: any) => <span>{r.transporter}</span> },
      { id: "pickupWindow", header: "Pickup Window", cell: (r: any) => <span>{r.pickupWindow}</span> },
      { id: "status", header: "Status", cell: (r: any) => <StatusBadge status={r.status} size="sm" /> },
    ],
    dataRows: [
      { id: "1", ref: "SHP-2026-9201", origin: "Chicago Dock 4", destination: "Dallas DC", transporter: "Apex Freight", pickupWindow: "14:00 - 16:00", status: "PICKUP_COMMITTED" },
      { id: "2", ref: "SHP-2026-9202", origin: "Detroit Hub", destination: "Atlanta Staging", transporter: "Vanguard", pickupWindow: "15:00 - 17:00", status: "DISPATCHED" },
      { id: "3", ref: "SHP-2026-9203", origin: "Cleveland Yard", destination: "Kansas City", transporter: "BlueStar", pickupWindow: "11:00 - 13:00", status: "IN_TRANSIT" },
      { id: "4", ref: "SHP-2026-9204", origin: "Gary Mill #1", destination: "Pittsburgh Terminal", transporter: "Titan Haulers", pickupWindow: "10:30 - 12:00", status: "DELIVERED" },
    ],
  },
  transporters: {
    title: "Transporters Directory",
    subtitle: "Manage authorized carrier network, insurance compliance, and SLA scorecards.",
    icon: <Truck className="h-5 w-5" />,
    primaryActionLabel: "Add Transporter",
    metric1: { title: "Contracted Carriers", value: "34", change: 3.1, trend: "up", period: "active networks" },
    metric2: { title: "Fleet Vehicles", value: "812", change: 12.0, trend: "up", period: "registered units" },
    metric3: { title: "On-Time Commitment", value: "96.4%", change: 1.8, trend: "up", period: "pickup adherence" },
    metric4: { title: "Pending Vetting", value: "2", trend: "neutral", period: "compliance review" },
    dataColumns: [
      { id: "name", header: "Carrier Name", cell: (r: any) => <span className="font-semibold text-slate-900">{r.name}</span> },
      { id: "mcDot", header: "MC / DOT #", cell: (r: any) => <span>{r.mcDot}</span> },
      { id: "lanes", header: "Primary Lanes", cell: (r: any) => <span>{r.lanes}</span> },
      { id: "fleetSize", header: "Fleet Capacity", cell: (r: any) => <span>{r.fleetSize}</span> },
      { id: "slaScore", header: "SLA Rating", cell: (r: any) => <span className="font-bold text-teal-600">{r.slaScore}</span> },
      { id: "status", header: "Status", cell: (r: any) => <StatusBadge status={r.status} size="sm" /> },
    ],
    dataRows: [
      { id: "1", name: "Apex Freight Express", mcDot: "MC-981240", lanes: "Midwest, Texas", fleetSize: "148 units", slaScore: "99.2%", status: "VERIFIED" },
      { id: "2", name: "Vanguard Logistics Group", mcDot: "MC-772194", lanes: "Great Lakes, Southeast", fleetSize: "230 units", slaScore: "97.8%", status: "VERIFIED" },
      { id: "3", name: "BlueStar Intermodal", mcDot: "MC-610943", lanes: "National Lanes", fleetSize: "320 units", slaScore: "95.4%", status: "VERIFIED" },
      { id: "4", name: "Titan Heavy Haul", mcDot: "MC-451029", lanes: "Ohio Valley", fleetSize: "64 units", slaScore: "88.1%", status: "AT_RISK" },
    ],
  },
  vehicles: {
    title: "Vehicle Fleet Management",
    subtitle: "Register, track, and inspect carrier tractors, trailers, and specialized units.",
    icon: <Car className="h-5 w-5" />,
    primaryActionLabel: "Register Vehicle",
    metric1: { title: "Active Vehicles", value: "624", trend: "up", period: "in network" },
    metric2: { title: "Assigned Right Now", value: "112", trend: "neutral", period: "currently under load" },
    metric3: { title: "Inspection Due", value: "8", change: -4, trend: "down", period: "next 14 days" },
    metric4: { title: "Utilization Rate", value: "88.4%", change: 3.2, trend: "up", period: "capacity factor" },
    dataColumns: [
      { id: "unitNo", header: "Vehicle Unit #", cell: (r: any) => <span className="font-semibold text-slate-900">{r.unitNo}</span> },
      { id: "type", header: "Vehicle Type", cell: (r: any) => <span>{r.type}</span> },
      { id: "carrier", header: "Carrier", cell: (r: any) => <span>{r.carrier}</span> },
      { id: "plate", header: "License Plate", cell: (r: any) => <span>{r.plate}</span> },
      { id: "telemetry", header: "GPS Telemetry", cell: (r: any) => <span className="text-teal-600 font-semibold">{r.telemetry}</span> },
      { id: "status", header: "Status", cell: (r: any) => <StatusBadge status={r.status} size="sm" /> },
    ],
    dataRows: [
      { id: "1", unitNo: "TRK-1049", type: "53' Dry Van", carrier: "Apex Freight", plate: "IL-4921-X", telemetry: "Active (5s ping)", status: "ASSIGNED" },
      { id: "2", unitNo: "TRK-2201", type: "Flatbed 48'", carrier: "Vanguard", plate: "MI-9102-B", telemetry: "Active (10s ping)", status: "AVAILABLE" },
      { id: "3", unitNo: "TRK-3342", type: "Refrigerated 53'", carrier: "BlueStar", plate: "IN-8821-C", telemetry: "Active (2s ping)", status: "ASSIGNED" },
    ],
  },
  drivers: {
    title: "Driver Management",
    subtitle: "Driver credentials, CDL compliance, assignment tracking, and check-in history.",
    icon: <Users2 className="h-5 w-5" />,
    primaryActionLabel: "Add Driver",
    metric1: { title: "Verified Drivers", value: "480", trend: "up", period: "active network" },
    metric2: { title: "On Active Trip", value: "96", trend: "neutral", period: "en-route" },
    metric3: { title: "Avg Rating", value: "4.89 / 5", trend: "up", period: "facility ratings" },
    metric4: { title: "License Expiry Due", value: "3", trend: "neutral", period: "next 30 days" },
    dataColumns: [
      { id: "name", header: "Driver Name", cell: (r: any) => <span className="font-semibold text-slate-900">{r.name}</span> },
      { id: "carrier", header: "Carrier", cell: (r: any) => <span>{r.carrier}</span> },
      { id: "cdl", header: "CDL Number", cell: (r: any) => <span>{r.cdl}</span> },
      { id: "phone", header: "Phone", cell: (r: any) => <span>{r.phone}</span> },
      { id: "safetyScore", header: "Safety Score", cell: (r: any) => <span className="font-bold text-teal-600">{r.safetyScore}</span> },
      { id: "status", header: "Status", cell: (r: any) => <StatusBadge status={r.status} size="sm" /> },
    ],
    dataRows: [
      { id: "1", name: "Marcus Higgins", carrier: "Apex Freight", cdl: "CDL-IL-98124", phone: "(312) 555-0192", safetyScore: "99.4%", status: "ACTIVE" },
      { id: "2", name: "Elena Rostova", carrier: "Vanguard", cdl: "CDL-MI-44910", phone: "(313) 555-0144", safetyScore: "98.1%", status: "ACTIVE" },
      { id: "3", name: "David Chen", carrier: "BlueStar", cdl: "CDL-IN-31092", phone: "(317) 555-0188", safetyScore: "97.5%", status: "ACTIVE" },
    ],
  },
  matching: {
    title: "Transporter Matching Engine",
    subtitle: "Algorithmic carrier scoring, lane ranking, and automated tender dispatch.",
    icon: <Sparkles className="h-5 w-5" />,
    primaryActionLabel: "Run Matching",
    metric1: { title: "Auto-Match Success", value: "94.8%", change: 2.3, trend: "up", period: "first tender pass" },
    metric2: { title: "Median Acceptance", value: "14 mins", change: -3.5, trend: "up", period: "vs benchmark" },
    metric3: { title: "Cost Efficiency", value: "+11.4%", change: 1.1, trend: "up", period: "route optimization" },
    metric4: { title: "Unmatched Loads", value: "2", trend: "neutral", period: "manual review" },
    dataColumns: [
      { id: "consignment", header: "Consignment Ref", cell: (r: any) => <span className="font-semibold text-blue-600">{r.consignment}</span> },
      { id: "route", header: "Lane Route", cell: (r: any) => <span>{r.route}</span> },
      { id: "recommendedCarrier", header: "Recommended Carrier", cell: (r: any) => <span>{r.recommendedCarrier}</span> },
      { id: "score", header: "Match Score", cell: (r: any) => <span className="font-bold text-teal-600">{r.score}</span> },
      { id: "status", header: "Tender Status", cell: (r: any) => <StatusBadge status={r.status} size="sm" /> },
    ],
    dataRows: [
      { id: "1", consignment: "SHP-2026-9201", route: "Chicago -> Dallas", recommendedCarrier: "Apex Freight Express", score: "98.4 / 100", status: "MATCHED" },
      { id: "2", consignment: "SHP-2026-9202", route: "Detroit -> Nashville", recommendedCarrier: "Vanguard Logistics", score: "96.1 / 100", status: "TENDERED" },
    ],
  },
  bookings: {
    title: "Bookings & Dispatch",
    subtitle: "Binding pickup commitments, dispatch confirmation, and SLA countdowns.",
    icon: <CalendarDays className="h-5 w-5" />,
    primaryActionLabel: "Create Booking",
    metric1: { title: "Active Bookings", value: "78", change: 4.2, trend: "up", period: "in execution" },
    metric2: { title: "Committed Today", value: "26", trend: "neutral", period: "100% SLA target" },
    metric3: { title: "Pending Response", value: "4", change: -2, trend: "down", period: "under 30m window" },
    metric4: { title: "Breach Rate", value: "0.4%", change: -0.2, trend: "up", period: "industry low" },
    dataColumns: [
      { id: "ref", header: "Booking Ref", cell: (r: any) => <span className="font-semibold text-slate-900">{r.ref}</span> },
      { id: "shipmentId", header: "Shipment ID", cell: (r: any) => <span>{r.shipmentId}</span> },
      { id: "carrier", header: "Transporter", cell: (r: any) => <span>{r.carrier}</span> },
      { id: "deadline", header: "Pickup Deadline", cell: (r: any) => <span>{r.deadline}</span> },
      { id: "status", header: "Commitment State", cell: (r: any) => <StatusBadge status={r.status} size="sm" /> },
    ],
    dataRows: [
      { id: "1", ref: "BKG-2026-4401", shipmentId: "SHP-2026-9201", carrier: "Apex Freight Express", deadline: "Today, 15:30 CST", status: "PICKUP_COMMITTED" },
      { id: "2", ref: "BKG-2026-4402", shipmentId: "SHP-2026-9202", carrier: "Vanguard Logistics", deadline: "Today, 17:00 EST", status: "DISPATCHED" },
    ],
  },
  "pickup-monitoring": {
    title: "Pickup Monitoring & Accountability",
    subtitle: "Real-time geofence tracking, gate arrival verification, and pickup SLA adherence.",
    icon: <Radio className="h-5 w-5" />,
    primaryActionLabel: "Check Gate Status",
    metric1: { title: "Vehicles at Facility", value: "14", trend: "neutral", period: "currently loading" },
    metric2: { title: "Arrivals on Schedule", value: "98.9%", change: 0.8, trend: "up", period: "within 15m window" },
    metric3: { title: "Avg Dock Dwell Time", value: "38 mins", change: -4.0, trend: "up", period: "fast turnaround" },
    metric4: { title: "Gate Breaches", value: "0", trend: "neutral", period: "today" },
    dataColumns: [
      { id: "dock", header: "Facility Dock", cell: (r: any) => <span className="font-semibold text-slate-900">{r.dock}</span> },
      { id: "vehicle", header: "Vehicle", cell: (r: any) => <span>{r.vehicle}</span> },
      { id: "driver", header: "Driver", cell: (r: any) => <span>{r.driver}</span> },
      { id: "arrival", header: "Arrival Timestamp", cell: (r: any) => <span>{r.arrival}</span> },
      { id: "status", header: "Dock State", cell: (r: any) => <StatusBadge status={r.status} size="sm" /> },
    ],
    dataRows: [
      { id: "1", dock: "Chicago Assembly Gate 4", vehicle: "TRK-1049", driver: "M. Higgins", arrival: "Today, 13:42 CST", status: "VEHICLE_ARRIVED" },
      { id: "2", dock: "Detroit Plant Dock 2", vehicle: "TRK-2201", driver: "E. Rostova", arrival: "Today, 14:10 EST", status: "PICKUP_COMMITTED" },
    ],
  },
  tracking: {
    title: "Live Shipment Tracking",
    subtitle: "GPS telemetry, geofence milestones, and real-time transit status.",
    icon: <MapPin className="h-5 w-5" />,
    primaryActionLabel: "Track Waybill",
    metric1: { title: "Active In-Transit", value: "89", trend: "neutral", period: "active telemetry" },
    metric2: { title: "On-Time ETA", value: "97.6%", change: 1.1, trend: "up", period: "predictive arrival" },
    metric3: { title: "Weather Delays", value: "1", trend: "neutral", period: "midwest corridor" },
    metric4: { title: "Avg Speed", value: "58 mph", trend: "neutral", period: "fleet average" },
    dataColumns: [
      { id: "ref", header: "Shipment Ref", cell: (r: any) => <span className="font-semibold text-blue-600">{r.ref}</span> },
      { id: "location", header: "Current GPS Location", cell: (r: any) => <span>{r.location}</span> },
      { id: "dest", header: "Destination Hub", cell: (r: any) => <span>{r.dest}</span> },
      { id: "eta", header: "Estimated Arrival", cell: (r: any) => <span>{r.eta}</span> },
      { id: "status", header: "Status", cell: (r: any) => <StatusBadge status={r.status} size="sm" /> },
    ],
    dataRows: [
      { id: "1", ref: "SHP-2026-9201", location: "I-55 South (Near Bloomington, IL)", dest: "Dallas DC", eta: "Tomorrow, 08:30 CST", status: "IN_TRANSIT" },
      { id: "2", ref: "SHP-2026-9203", location: "I-70 West (Near Terre Haute, IN)", dest: "Kansas City", eta: "Tomorrow, 14:00 CST", status: "IN_TRANSIT" },
    ],
  },
  exceptions: {
    title: "Exceptions & Escalations",
    subtitle: "Detect failed pickups, late arrivals, carrier cancellations, and automated recovery.",
    icon: <AlertTriangle className="h-5 w-5" />,
    primaryActionLabel: "Report Exception",
    metric1: { title: "Active Exceptions", value: "3", change: -2, trend: "up", period: "under active triage" },
    metric2: { title: "Automated Recovery", value: "87.5%", change: 5.0, trend: "up", period: "resolved without human" },
    metric3: { title: "Mean Resolution Time", value: "22 mins", change: -8.0, trend: "up", period: "reassignment speed" },
    metric4: { title: "Critical Escalations", value: "1", trend: "neutral", period: "urgent ops review" },
    dataColumns: [
      { id: "ref", header: "Exception Ref", cell: (r: any) => <span className="font-semibold text-rose-600">{r.ref}</span> },
      { id: "shipmentId", header: "Shipment ID", cell: (r: any) => <span>{r.shipmentId}</span> },
      { id: "reason", header: "Exception Reason", cell: (r: any) => <span>{r.reason}</span> },
      { id: "carrier", header: "Fault Carrier", cell: (r: any) => <span>{r.carrier}</span> },
      { id: "recovery", header: "Recovery Plan", cell: (r: any) => <span>{r.recovery}</span> },
      { id: "status", header: "Severity", cell: (r: any) => <StatusBadge status={r.status} size="sm" /> },
    ],
    dataRows: [
      { id: "1", ref: "EXC-2026-104", shipmentId: "SHP-2026-9106", reason: "Vehicle Breakdown / No-Show", carrier: "Titan Heavy Haul", recovery: "AI auto-reroute to BlueStar", status: "CRITICAL" },
      { id: "2", ref: "EXC-2026-103", shipmentId: "SHP-2026-8994", reason: "Loading Gate Congestion (>60m)", carrier: "Apex Freight", recovery: "Dock priority pass issued", status: "WARNING" },
    ],
  },
  "ai-coordinator": {
    title: "AI Logistics Coordinator",
    subtitle: "Autonomous recovery agent, intelligent load tender, and predictive risk scoring.",
    icon: <Bot className="h-5 w-5" />,
    primaryActionLabel: "Run Diagnostic Scan",
    metric1: { title: "Autonomous Decisions", value: "348", change: 24.0, trend: "up", period: "actions logged this week" },
    metric2: { title: "Recovery Success", value: "98.2%", change: 1.4, trend: "up", period: "zero human intervention" },
    metric3: { title: "Hours Saved", value: "114 hrs", trend: "up", period: "dispatch workload" },
    metric4: { title: "Confidence Score", value: "99.4%", trend: "up", period: "model precision" },
    dataColumns: [
      { id: "id", header: "Action ID", cell: (r: any) => <span className="font-mono text-xs font-bold text-slate-800">{r.id}</span> },
      { id: "target", header: "Target Entity", cell: (r: any) => <span>{r.target}</span> },
      { id: "type", header: "Decision Type", cell: (r: any) => <span>{r.type}</span> },
      { id: "rationale", header: "Decision Rationale", cell: (r: any) => <span>{r.rationale}</span> },
      { id: "status", header: "Execution Result", cell: (r: any) => <StatusBadge status={r.status} size="sm" /> },
    ],
    dataRows: [
      { id: "ACT-AI-902", target: "SHP-2026-9106", type: "Dynamic Reroute", rationale: "Primary carrier failed window; nearest eligible carrier matched in 40m", status: "EXECUTED" },
      { id: "ACT-AI-901", target: "BKG-2026-4399", type: "Proactive Escalation", rationale: "Driver speed anomaly detected; revised ETA notified to consignee", status: "NOTIFIED" },
    ],
  },
  "proof-of-delivery": {
    title: "Proof of Delivery (POD)",
    subtitle: "Electronic signatures, bills of lading, freight photos, and receiving discrepancies.",
    icon: <FileCheck2 className="h-5 w-5" />,
    primaryActionLabel: "Upload POD",
    metric1: { title: "Verified Deliveries", value: "1,240", change: 18.0, trend: "up", period: "this month" },
    metric2: { title: "Digital POD Rate", value: "100%", trend: "neutral", period: "paperless platform" },
    metric3: { title: "Discrepancy Rate", value: "0.2%", change: -0.1, trend: "up", period: "tamper verified" },
    metric4: { title: "Avg Close Time", value: "4 mins", trend: "up", period: "instant verification" },
    dataColumns: [
      { id: "id", header: "POD Document ID", cell: (r: any) => <span className="font-semibold text-slate-900">{r.id}</span> },
      { id: "shipmentRef", header: "Shipment Ref", cell: (r: any) => <span>{r.shipmentRef}</span> },
      { id: "signatory", header: "Signatory", cell: (r: any) => <span>{r.signatory}</span> },
      { id: "timestamp", header: "Delivery Timestamp", cell: (r: any) => <span>{r.timestamp}</span> },
      { id: "discrepancies", header: "Discrepancies", cell: (r: any) => <span>{r.discrepancies}</span> },
      { id: "status", header: "Status", cell: (r: any) => <StatusBadge status={r.status} size="sm" /> },
    ],
    dataRows: [
      { id: "POD-2026-8801", shipmentRef: "SHP-2026-8992", signatory: "J. Doe (Receiving Mgr)", timestamp: "Today, 11:32 EST", discrepancies: "None (100% Match)", status: "VERIFIED" },
      { id: "POD-2026-8802", shipmentRef: "SHP-2026-8980", signatory: "R. Smith (Dock Lead)", timestamp: "Yesterday, 16:45 CST", discrepancies: "1 damaged carton flagged", status: "DISCREPANCY" },
    ],
  },
  reconciliation: {
    title: "Billing & Freight Reconciliation",
    subtitle: "Automated invoice three-way matching, detention claims, and payment authorization.",
    icon: <Receipt className="h-5 w-5" />,
    primaryActionLabel: "Reconcile Batch",
    metric1: { title: "Auto-Reconciled", value: "$428,000", change: 9.2, trend: "up", period: "last 30 days" },
    metric2: { title: "Matched First Pass", value: "98.7%", change: 0.5, trend: "up", period: "zero discrepancy" },
    metric3: { title: "Pending Claims", value: "$1,450", change: -12.0, trend: "up", period: "detention charges" },
    metric4: { title: "Audit Ready", value: "100%", trend: "neutral", period: "SOX compliant" },
    dataColumns: [
      { id: "ref", header: "Invoice Ref", cell: (r: any) => <span className="font-semibold text-slate-900">{r.ref}</span> },
      { id: "carrier", header: "Carrier", cell: (r: any) => <span>{r.carrier}</span> },
      { id: "shipmentId", header: "Shipment ID", cell: (r: any) => <span>{r.shipmentId}</span> },
      { id: "contractCost", header: "Contracted Cost", cell: (r: any) => <span>{r.contractCost}</span> },
      { id: "billedCost", header: "Billed Cost", cell: (r: any) => <span>{r.billedCost}</span> },
      { id: "status", header: "Reconciliation", cell: (r: any) => <StatusBadge status={r.status} size="sm" /> },
    ],
    dataRows: [
      { id: "1", ref: "INV-2026-5501", carrier: "Apex Freight Express", shipmentId: "SHP-2026-8992", contractCost: "$2,850.00", billedCost: "$2,850.00", status: "MATCHED" },
      { id: "2", ref: "INV-2026-5502", carrier: "Titan Heavy Haul", shipmentId: "SHP-2026-8910", contractCost: "$1,900.00", billedCost: "$2,100.00", status: "DISCREPANCY" },
    ],
  },
  analytics: {
    title: "Operational Analytics & Insights",
    subtitle: "Enterprise freight performance, carrier scorecards, cost trends, and SLA forecasting.",
    icon: <BarChart3 className="h-5 w-5" />,
    primaryActionLabel: "Export Report",
    metric1: { title: "Monthly Freight Volume", value: "1,840 tons", change: 14.2, trend: "up", period: "vs last month" },
    metric2: { title: "Average Transit Time", value: "18.4 hrs", change: -2.1, trend: "up", period: "improved speed" },
    metric3: { title: "Carrier SLA Index", value: "98.4 / 100", change: 1.0, trend: "up", period: "aggregate network" },
    metric4: { title: "Freight Cost / Ton-Mile", value: "$0.142", change: -3.8, trend: "up", period: "lower unit cost" },
    dataColumns: [
      { id: "lane", header: "Operating Lane", cell: (r: any) => <span className="font-semibold text-slate-900">{r.lane}</span> },
      { id: "volume", header: "Monthly Volume", cell: (r: any) => <span>{r.volume}</span> },
      { id: "carrier", header: "Preferred Carrier", cell: (r: any) => <span>{r.carrier}</span> },
      { id: "sla", header: "On-Time SLA", cell: (r: any) => <span className="font-bold text-teal-600">{r.sla}</span> },
      { id: "efficiency", header: "Cost Efficiency", cell: (r: any) => <span>{r.efficiency}</span> },
    ],
    dataRows: [
      { id: "1", lane: "Chicago, IL -> Dallas, TX", volume: "42 loads", carrier: "Apex Freight Express", sla: "99.2%", efficiency: "+8.4% vs benchmark" },
      { id: "2", lane: "Detroit, MI -> Nashville, TN", volume: "38 loads", carrier: "Vanguard Logistics", sla: "98.1%", efficiency: "+6.1% vs benchmark" },
    ],
  },
  integrations: {
    title: "Enterprise Integrations",
    subtitle: "Connect ERPs, TMS systems, WMS facilities, GPS telematics, and EDI/REST webhooks.",
    icon: <Cable className="h-5 w-5" />,
    primaryActionLabel: "Add Connection",
    metric1: { title: "Active Connectors", value: "6", trend: "up", period: "ERP & TMS links" },
    metric2: { title: "Daily API Volume", value: "184,200", change: 12.0, trend: "up", period: "synced events" },
    metric3: { title: "Webhook Success Rate", value: "99.98%", trend: "neutral", period: "zero drop" },
    metric4: { title: "Sync Latency", value: "48 ms", trend: "up", period: "real-time streaming" },
    dataColumns: [
      { id: "system", header: "Integration System", cell: (r: any) => <span className="font-semibold text-slate-900">{r.system}</span> },
      { id: "protocol", header: "Protocol", cell: (r: any) => <span>{r.protocol}</span> },
      { id: "lastSync", header: "Last Synced", cell: (r: any) => <span>{r.lastSync}</span> },
      { id: "status", header: "Health Status", cell: (r: any) => <StatusBadge status={r.status} size="sm" /> },
    ],
    dataRows: [
      { id: "1", system: "SAP S/4HANA Enterprise ERP", protocol: "REST & Webhook", lastSync: "1 min ago", status: "CONNECTED" },
      { id: "2", system: "Samsara Fleet GPS Telematics", protocol: "OAuth2 Stream", lastSync: "Live (5s)", status: "CONNECTED" },
      { id: "3", system: "Manhattan WMS Facility Dock", protocol: "EDI 214 / REST", lastSync: "4 mins ago", status: "CONNECTED" },
    ],
  },
  "audit-trail": {
    title: "Cryptographic Audit Trail",
    subtitle: "Immutable append-only operational event ledger with cryptographic hash chaining.",
    icon: <ShieldCheck className="h-5 w-5" />,
    primaryActionLabel: "Verify Ledger Integrity",
    metric1: { title: "Logged Events", value: "842,109", trend: "up", period: "tamper-proof records" },
    metric2: { title: "Chain Integrity", value: "100% VALID", trend: "up", period: "SHA-256 verified" },
    metric3: { title: "Compliance Status", value: "CERTIFIED", trend: "neutral", period: "SOC2 Type II / ISO" },
    metric4: { title: "Security Alerts", value: "0", trend: "neutral", period: "all signatures clean" },
    dataColumns: [
      { id: "hash", header: "Audit Event Hash", cell: (r: any) => <span className="font-mono text-xs text-blue-600 truncate">{r.hash}</span> },
      { id: "eventType", header: "Event Type", cell: (r: any) => <span>{r.eventType}</span> },
      { id: "actor", header: "Actor / Identity", cell: (r: any) => <span>{r.actor}</span> },
      { id: "timestamp", header: "Timestamp (UTC)", cell: (r: any) => <span>{r.timestamp}</span> },
      { id: "status", header: "Verification", cell: (r: any) => <StatusBadge status={r.status} size="sm" /> },
    ],
    dataRows: [
      { id: "1", hash: "0x7f88a912c9b4e101...", eventType: "SHIPMENT_DISPATCH_AUTHORIZED", actor: "dispatch.lead@apex.com", timestamp: "2026-11-21 08:45:12", status: "VERIFIED" },
      { id: "2", hash: "0x3e1104b2a8d9f441...", eventType: "PICKUP_COMMITMENT_RATIFIED", actor: "carrier.apex@freight.com", timestamp: "2026-11-21 08:30:00", status: "VERIFIED" },
    ],
  },
};

export const ModulePlaceholderPage: React.FC = () => {
  const location = useLocation();
  const { addToast } = useToast();
  const [searchQuery, setSearchQuery] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Extract module key from pathname (e.g. "/shipments" -> "shipments")
  const moduleKey = location.pathname.replace(/^\//, "").split("/")[0] || "shipments";
  const config = MODULE_REGISTRY[moduleKey] || MODULE_REGISTRY["shipments"];
  const IconNode = config.icon;

  const handleRefresh = () => {
    setIsRefreshing(true);
    setTimeout(() => {
      setIsRefreshing(false);
      addToast({
        title: `${config.title} Refreshed`,
        description: "Latest operational status and records loaded.",
        type: "info",
      });
    }, 500);
  };

  const handlePrimaryAction = () => {
    addToast({
      title: `${config.primaryActionLabel} Initiated`,
      description: `Action dispatched for ${config.title}.`,
      type: "success",
    });
  };

  const filteredData = useMemo(() => {
    if (!searchQuery.trim()) return config.dataRows;
    const q = searchQuery.toLowerCase();
    return config.dataRows.filter((row) =>
      Object.values(row).some((val) => String(val).toLowerCase().includes(q))
    );
  }, [config.dataRows, searchQuery]);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title={config.title}
        subtitle={config.subtitle}
        breadcrumbs={[
          { label: "Console", href: "/overview" },
          { label: config.title },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="gap-1.5"
            >
              <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
              Refresh
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={handlePrimaryAction}
              className="gap-1.5"
            >
              <Plus className="h-4 w-4" />
              {config.primaryActionLabel}
            </Button>
          </div>
        }
      />

      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title={config.metric1.title}
          value={config.metric1.value}
          change={config.metric1.change}
          trend={config.metric1.trend || "neutral"}
          period={config.metric1.period}
          icon={IconNode}
          accentColor="blue"
        />
        <MetricCard
          title={config.metric2.title}
          value={config.metric2.value}
          change={config.metric2.change}
          trend={config.metric2.trend || "neutral"}
          period={config.metric2.period}
          icon={IconNode}
          accentColor="teal"
        />
        <MetricCard
          title={config.metric3.title}
          value={config.metric3.value}
          change={config.metric3.change}
          trend={config.metric3.trend || "neutral"}
          period={config.metric3.period}
          icon={IconNode}
          accentColor="blue"
        />
        <MetricCard
          title={config.metric4.title}
          value={config.metric4.value}
          change={config.metric4.change}
          trend={config.metric4.trend || "neutral"}
          period={config.metric4.period}
          icon={IconNode}
          accentColor="amber"
        />
      </div>

      {/* Main Data Section */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-xs p-4 sm:p-5 space-y-4">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-bold text-slate-900">{config.title} Records</h3>
            <p className="text-xs text-slate-500">Live operational ledger for this tenant module.</p>
          </div>

          <div className="flex items-center gap-2">
            <SearchBar
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder="Search records..."
              className="w-full sm:w-64"
            />
          </div>
        </div>

        {/* Data Table */}
        <DataTable
          columns={config.dataColumns}
          data={filteredData}
          keyExtractor={(row: any) => row.id}
          selectable
          emptyTitle="No records found"
          emptyDescription={`There are currently no records matching "${searchQuery}".`}
        />
      </div>
    </div>
  );
};
