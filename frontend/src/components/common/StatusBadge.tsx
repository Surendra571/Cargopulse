import React from "react";
import { cn } from "@/lib/utils";

export type EntityStatus =
  // Shipment statuses
  | "DRAFT"
  | "PENDING_ACCEPTANCE"
  | "COMMITTED"
  | "DISPATCHED"
  | "AT_PICKUP"
  | "IN_TRANSIT"
  | "OUT_FOR_DELIVERY"
  | "DELIVERED"
  | "EXCEPTION"
  | "CANCELLED"
  // Booking statuses
  | "REQUESTED"
  | "ACCEPTED"
  | "REJECTED"
  | "EXPIRED"
  // Generic & Verification
  | "ACTIVE"
  | "INACTIVE"
  | "SUSPENDED"
  | "PENDING"
  | "REGISTERED"
  | "DOCUMENTS_SUBMITTED"
  | "UNDER_VERIFICATION"
  | "VERIFIED"
  | "MAINTENANCE"
  | "EXPIRED_DOCUMENTS"
  | "EXPIRED_LICENSE"
  | "ON_DUTY"
  | "OFF_DUTY"
  | "RESOLVED"
  | "CRITICAL"
  | "HIGH"
  | "MEDIUM"
  | "LOW"
  | string;

interface StatusConfig {
  label: string;
  dotColor: string;
  badgeClass: string;
}

const statusMap: Record<string, StatusConfig> = {
  // Shipments
  DRAFT: {
    label: "Draft",
    dotColor: "bg-on-surface-subtle",
    badgeClass: "bg-surface-container-low text-on-surface-muted border-outline-variant",
  },
  PENDING_ACCEPTANCE: {
    label: "Pending Acceptance",
    dotColor: "bg-warning",
    badgeClass: "bg-warning-container text-on-warning-container border-warning/20",
  },
  COMMITTED: {
    label: "Committed",
    dotColor: "bg-success",
    badgeClass: "bg-success-container text-on-success-container border-success/20",
  },
  DISPATCHED: {
    label: "Dispatched",
    dotColor: "bg-secondary",
    badgeClass: "bg-secondary-container text-on-secondary-container border-outline-variant",
  },
  AT_PICKUP: {
    label: "At Pickup Facility",
    dotColor: "bg-success",
    badgeClass: "bg-success-container text-on-success-container border-success/20",
  },
  IN_TRANSIT: {
    label: "In Transit",
    dotColor: "bg-burnt-orange",
    badgeClass: "bg-primary-container text-on-primary-container border-burnt-orange/20",
  },
  OUT_FOR_DELIVERY: {
    label: "Out For Delivery",
    dotColor: "bg-success",
    badgeClass: "bg-success-container text-on-success-container border-success/20",
  },
  DELIVERED: {
    label: "Delivered",
    dotColor: "bg-success",
    badgeClass: "bg-success-container text-on-success-container border-success/30 font-semibold",
  },
  EXCEPTION: {
    label: "Exception Alert",
    dotColor: "bg-critical",
    badgeClass: "bg-critical-container text-on-critical-container border-critical/30 font-semibold",
  },
  CANCELLED: {
    label: "Cancelled",
    dotColor: "bg-on-surface-subtle",
    badgeClass: "bg-surface-container text-on-surface-muted border-outline-variant line-through",
  },

  // Booking
  REQUESTED: {
    label: "Requested",
    dotColor: "bg-warning",
    badgeClass: "bg-warning-container text-on-warning-container border-warning/20",
  },
  ACCEPTED: {
    label: "Accepted",
    dotColor: "bg-success",
    badgeClass: "bg-success-container text-on-success-container border-success/20",
  },
  CONFIRMED: {
    label: "Confirmed",
    dotColor: "bg-success",
    badgeClass: "bg-success-container text-on-success-container border-success/20 font-semibold",
  },
  REJECTED: {
    label: "Rejected",
    dotColor: "bg-critical",
    badgeClass: "bg-critical-container text-on-critical-container border-critical/20",
  },
  EXPIRED: {
    label: "Expired",
    dotColor: "bg-on-surface-subtle",
    badgeClass: "bg-surface-container-low text-on-surface-muted border-outline-variant",
  },

  // Generic
  ACTIVE: {
    label: "Active",
    dotColor: "bg-success-container0",
    badgeClass: "bg-success-container text-on-success-container border-emerald-200",
  },
  INACTIVE: {
    label: "Inactive",
    dotColor: "bg-slate-400",
    badgeClass: "bg-surface-container text-on-surface-muted border-outline-variant",
  },
  SUSPENDED: {
    label: "Suspended",
    dotColor: "bg-critical-container0",
    badgeClass: "bg-critical-container text-on-critical-container border-rose-200",
  },
  REGISTERED: {
    label: "Registered",
    dotColor: "bg-slate-400",
    badgeClass: "bg-surface-container text-on-surface border-outline-variant",
  },
  DOCUMENTS_SUBMITTED: {
    label: "Docs Submitted",
    dotColor: "bg-primary-container0",
    badgeClass: "bg-primary-container text-primary border-burnt-orange/30",
  },
  UNDER_VERIFICATION: {
    label: "Under Verification",
    dotColor: "bg-warning-container0 animate-pulse",
    badgeClass: "bg-warning-container text-on-warning-container border-amber-200",
  },
  MAINTENANCE: {
    label: "Maintenance",
    dotColor: "bg-warning-container0",
    badgeClass: "bg-warning-container text-on-warning-container border-amber-200",
  },
  EXPIRED_DOCUMENTS: {
    label: "Expired Docs",
    dotColor: "bg-critical-container0",
    badgeClass: "bg-critical-container text-on-critical-container border-rose-300 font-semibold",
  },
  EXPIRED_LICENSE: {
    label: "Expired License",
    dotColor: "bg-critical-container0",
    badgeClass: "bg-critical-container text-on-critical-container border-rose-300 font-semibold",
  },
  ON_DUTY: {
    label: "On Duty",
    dotColor: "bg-success-container0",
    badgeClass: "bg-success-container text-on-success-container border-emerald-200",
  },
  OFF_DUTY: {
    label: "Off Duty",
    dotColor: "bg-slate-400",
    badgeClass: "bg-surface-container text-on-surface-muted border-outline-variant",
  },
  VERIFIED: {
    label: "Verified",
    dotColor: "bg-teal-600",
    badgeClass: "bg-success-container text-teal-800 border-teal-300",
  },
  RESOLVED: {
    label: "Resolved",
    dotColor: "bg-primary",
    badgeClass: "bg-primary-container text-primary border-burnt-orange/30",
  },
  CRITICAL: {
    label: "Critical",
    dotColor: "bg-rose-600",
    badgeClass: "bg-rose-100 text-rose-800 border-rose-300 font-bold",
  },
  HIGH: {
    label: "High",
    dotColor: "bg-amber-600",
    badgeClass: "bg-amber-100 text-amber-800 border-amber-300 font-semibold",
  },
  MEDIUM: {
    label: "Medium",
    dotColor: "bg-primary-container0",
    badgeClass: "bg-primary-container text-primary border-burnt-orange/30",
  },
  // Pickup Commitment statuses
  REMINDER_SENT: {
    label: "Reminder Sent",
    dotColor: "bg-primary-container0",
    badgeClass: "bg-primary-container text-primary border-burnt-orange/30",
  },
  AT_RISK: {
    label: "At Risk (10m SLA)",
    dotColor: "bg-warning-container0 animate-pulse",
    badgeClass: "bg-warning-container text-amber-800 border-amber-300 font-semibold",
  },
  ARRIVED: {
    label: "Arrived at Dock",
    dotColor: "bg-indigo-500",
    badgeClass: "bg-indigo-50 text-indigo-700 border-indigo-200",
  },
  STARTED: {
    label: "Loading Started",
    dotColor: "bg-success-container0",
    badgeClass: "bg-success-container text-on-success-container border-teal-200",
  },
  COMPLETED: {
    label: "Pickup Completed",
    dotColor: "bg-success-container0",
    badgeClass: "bg-success-container text-on-success-container border-emerald-200",
  },
  MISSED: {
    label: "Missed Pickup",
    dotColor: "bg-rose-600 animate-ping",
    badgeClass: "bg-rose-100 text-rose-800 border-rose-300 font-bold",
  },

  // Exception Lifecycle
  OPEN: {
    label: "Open Incident",
    dotColor: "bg-critical-container0",
    badgeClass: "bg-critical-container text-on-critical-container border-rose-200 font-semibold",
  },
  ACKNOWLEDGED: {
    label: "Acknowledged",
    dotColor: "bg-warning-container0",
    badgeClass: "bg-warning-container text-on-warning-container border-amber-200",
  },
  INVESTIGATING: {
    label: "Investigating",
    dotColor: "bg-primary-container0",
    badgeClass: "bg-primary-container text-primary border-burnt-orange/30",
  },
  RESOLVING: {
    label: "Resolving",
    dotColor: "bg-purple-500",
    badgeClass: "bg-purple-50 text-purple-700 border-purple-200",
  },
  CLOSED: {
    label: "Closed",
    dotColor: "bg-slate-400",
    badgeClass: "bg-surface-container text-on-surface-muted border-outline-variant",
  },
  REASSIGNED: {
    label: "Reassigned",
    dotColor: "bg-purple-500",
    badgeClass: "bg-purple-50 text-purple-700 border-purple-200",
  },

  LOW: {
    label: "Low",
    dotColor: "bg-slate-400",
    badgeClass: "bg-surface-container text-on-surface-muted border-outline-variant",
  },
};

export interface StatusBadgeProps {
  status: EntityStatus;
  size?: "sm" | "default";
  showDot?: boolean;
  className?: string;
  customLabel?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  size = "default",
  showDot = true,
  className,
  customLabel,
}) => {
  const normalizedKey = status ? String(status).toUpperCase() : "DRAFT";
  const config = statusMap[normalizedKey] || {
    label: customLabel || normalizedKey.replace(/_/g, " "),
    dotColor: "bg-slate-400",
    badgeClass: "bg-surface-container text-on-surface border-outline-variant",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium select-none tracking-tight",
        size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-0.5 text-xs",
        config.badgeClass,
        className
      )}
    >
      {showDot && (
        <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", config.dotColor)} />
      )}
      <span>{customLabel || config.label}</span>
    </span>
  );
};
