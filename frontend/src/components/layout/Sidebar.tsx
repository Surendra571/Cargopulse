import React from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { ChevronLeft, ChevronRight, X } from "lucide-react";

export interface NavItemConfig {
  title: string;
  path: string;
  iconName: string;
  requiredPermissions?: string[];
  allowedRoles?: string[];
  badge?: string | number;
  badgeVariant?: "warning" | "critical" | "primary" | "success";
}

export interface NavGroupConfig {
  label: string;
  items: NavItemConfig[];
}

const NAVIGATION_GROUPS: NavGroupConfig[] = [
  {
    label: "OVERVIEW",
    items: [
      {
        title: "Operations Dashboard",
        path: "/overview",
        iconName: "dashboard",
      },
    ],
  },
  {
    label: "SHIPMENT OPERATIONS",
    items: [
      {
        title: "Shipments",
        path: "/shipments",
        iconName: "inventory_2",
      },
      {
        title: "Transporters",
        path: "/transporters",
        iconName: "local_shipping",
        allowedRoles: ["SUPER_ADMIN", "ORGANIZATION_ADMIN", "DISPATCH_MANAGER", "OPERATIONS_MANAGER"],
      },
      {
        title: "Vehicles",
        path: "/vehicles",
        iconName: "directions_bus",
        allowedRoles: ["SUPER_ADMIN", "ORGANIZATION_ADMIN", "TRANSPORTER_ADMIN", "OPERATIONS_MANAGER"],
      },
      {
        title: "Drivers",
        path: "/drivers",
        iconName: "badge",
        allowedRoles: ["SUPER_ADMIN", "ORGANIZATION_ADMIN", "TRANSPORTER_ADMIN", "OPERATIONS_MANAGER"],
      },
      {
        title: "Transporter Matching",
        path: "/matching",
        iconName: "compare_arrows",
        allowedRoles: ["SUPER_ADMIN", "ORGANIZATION_ADMIN", "DISPATCH_MANAGER"],
      },
      {
        title: "Bookings",
        path: "/bookings",
        iconName: "event_available",
      },
    ],
  },
  {
    label: "MONITORING",
    items: [
      {
        title: "Pickup Monitoring",
        path: "/pickup-monitoring",
        iconName: "schedule",
      },
      {
        title: "Shipment Tracking",
        path: "/tracking",
        iconName: "route",
      },
      {
        title: "Exceptions",
        path: "/exceptions",
        iconName: "warning",
      },
      {
        title: "Recovery Center",
        path: "/recovery",
        iconName: "autorenew",
      },
      {
        title: "Proof of Delivery",
        path: "/proof-of-delivery",
        iconName: "fact_check",
      },
    ],
  },
  {
    label: "INTELLIGENCE",
    items: [
      {
        title: "AI Coordinator",
        path: "/ai-coordinator",
        iconName: "smart_toy",
      },
      {
        title: "Reconciliation",
        path: "/reconciliation",
        iconName: "balance",
        allowedRoles: ["SUPER_ADMIN", "ORGANIZATION_ADMIN", "OPERATIONS_MANAGER"],
      },
      {
        title: "Analytics",
        path: "/analytics",
        iconName: "analytics",
        allowedRoles: ["SUPER_ADMIN", "ORGANIZATION_ADMIN", "OPERATIONS_MANAGER", "DISPATCH_MANAGER"],
      },
    ],
  },
  {
    label: "SYSTEM",
    items: [
      {
        title: "Integrations",
        path: "/integrations",
        iconName: "hub",
        allowedRoles: ["SUPER_ADMIN", "ORGANIZATION_ADMIN", "DISPATCH_MANAGER", "OPERATIONS_MANAGER"],
      },
      {
        title: "Webhook Monitor",
        path: "/integrations/webhooks",
        iconName: "webhook",
        allowedRoles: ["SUPER_ADMIN", "ORGANIZATION_ADMIN", "DISPATCH_MANAGER", "OPERATIONS_MANAGER"],
      },
      {
        title: "Retry Queue",
        path: "/integrations/retry-queue",
        iconName: "replay",
        allowedRoles: ["SUPER_ADMIN", "ORGANIZATION_ADMIN", "DISPATCH_MANAGER", "OPERATIONS_MANAGER"],
      },
      {
        title: "Dead Letter Queue",
        path: "/integrations/dlq",
        iconName: "error_outline",
        allowedRoles: ["SUPER_ADMIN", "ORGANIZATION_ADMIN", "DISPATCH_MANAGER", "OPERATIONS_MANAGER"],
      },
      {
        title: "Audit Trail",
        path: "/audit-trail",
        iconName: "history",
        allowedRoles: ["SUPER_ADMIN", "ORGANIZATION_ADMIN", "OPERATIONS_MANAGER"],
      },
      {
        title: "Settings",
        path: "/organization",
        iconName: "settings",
        allowedRoles: ["SUPER_ADMIN", "ORGANIZATION_ADMIN"],
      },
    ],
  },
];

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
}) => {
  const { user } = useAuth();

  const isItemVisible = (item: NavItemConfig): boolean => {
    if (!user) return false;
    if (user.is_superadmin) return true;

    if (item.allowedRoles && item.allowedRoles.length > 0) {
      const userRoles = user.roles || [];
      const hasRole = item.allowedRoles.some((role) =>
        userRoles.some((r) => r.toUpperCase().includes(role) || role.includes(r.toUpperCase()))
      );
      if (!hasRole) return false;
    }

    if (item.requiredPermissions && item.requiredPermissions.length > 0) {
      const userPerms = user.permissions || [];
      const hasPerm = item.requiredPermissions.some((p) => userPerms.includes(p));
      if (!hasPerm) return false;
    }

    return true;
  };

  const badgeColorClass = (variant?: string) => {
    switch (variant) {
      case "warning":
        return "bg-warning-container text-on-warning-container";
      case "critical":
        return "bg-critical text-on-critical";
      case "primary":
        return "bg-primary text-on-primary";
      case "success":
      default:
        return "bg-success-container text-on-success-container";
    }
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-secondary/40 lg:hidden transition-opacity duration-surface-enter"
          onClick={onCloseMobile}
        />
      )}

      {/* Persistent Light Warm-Orange Sidebar */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-40 flex flex-col justify-between bg-sidebar text-on-sidebar border-r border-outline-variant transition-all duration-surface-enter ease-surface-enter ${
          collapsed ? "lg:w-[72px]" : "lg:w-64"
        } ${mobileOpen ? "translate-x-0 w-64" : "-translate-x-full lg:translate-x-0"}`}
      >
        <div className="flex flex-col min-h-0 flex-1">
          {/* Brand Header */}
          <div className="h-16 px-4 flex items-center justify-between border-b border-outline-strong shrink-0">
            <div className="flex items-center gap-2.5 overflow-hidden">
              <div className="w-8 h-8 rounded-sm bg-surface-card flex items-center justify-center border border-outline-variant shrink-0">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M3 7.5L12 3L21 7.5V16.5L12 21L3 16.5V7.5Z"
                    stroke="#253447"
                    strokeWidth="2"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M12 12L21 7.5M12 12V21M12 12L3 7.5"
                    stroke="#253447"
                    strokeWidth="2"
                    strokeLinejoin="round"
                  />
                  <circle cx="12" cy="12" r="2.2" fill="#D97736" />
                </svg>
              </div>

              {(!collapsed || mobileOpen) && (
                <div className="min-w-0">
                  <span className="font-headline text-title-md text-on-sidebar block leading-none truncate">
                    CargoPulse
                  </span>
                  <span className="font-label text-label-sm text-on-sidebar opacity-80 block truncate">
                    Accountable Freight
                  </span>
                </div>
              )}
            </div>

            <button
              type="button"
              onClick={onCloseMobile}
              className="lg:hidden p-1.5 text-on-sidebar hover:bg-sidebar-hover rounded-sm transition-colors duration-state-change"
              aria-label="Close navigation"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Primary Navigation */}
          <nav aria-label="Primary navigation" className="flex-1 overflow-y-auto p-3 flex flex-col gap-5">
            {NAVIGATION_GROUPS.map((group) => {
              const visibleItems = group.items.filter(isItemVisible);
              if (visibleItems.length === 0) return null;

              return (
                <div key={group.label}>
                  {(!collapsed || mobileOpen) && (
                    <p className="px-3 mb-1.5 font-label text-label-sm text-on-sidebar opacity-95 tracking-wider">
                      {group.label}
                    </p>
                  )}

                  <ul className="flex flex-col gap-0.5">
                    {visibleItems.map((item) => (
                      <li key={item.path}>
                        <NavLink
                          to={item.path}
                          end={item.path === "/integrations"}
                          onClick={() => {
                            if (mobileOpen) onCloseMobile();
                          }}
                          title={collapsed && !mobileOpen ? item.title : undefined}
                          className={({ isActive }) =>
                            `flex items-center justify-between px-3 rounded-sm transition-colors duration-state-change ${
                              isActive
                                ? "py-2 bg-sidebar-active text-on-surface font-label text-label-md border border-outline-variant"
                                : "py-1.5 text-on-sidebar font-body text-body-sm hover:bg-sidebar-hover"
                            } ${collapsed && !mobileOpen ? "justify-center px-0" : ""}`
                          }
                        >
                          {({ isActive }) => (
                            <>
                              <span className="flex items-center gap-2.5 min-w-0">
                                <span
                                  className={`material-symbols-outlined text-[18px] shrink-0 ${
                                    isActive ? "text-burnt-orange" : "text-on-sidebar"
                                  }`}
                                  aria-hidden="true"
                                >
                                  {item.iconName}
                                </span>
                                {(!collapsed || mobileOpen) && (
                                  <span className="truncate">{item.title}</span>
                                )}
                              </span>

                              {(!collapsed || mobileOpen) && item.badge !== undefined && (
                                <span
                                  className={`px-1.5 py-0.5 rounded-full font-label text-label-sm tabular-nums ${badgeColorClass(
                                    item.badgeVariant
                                  )}`}
                                >
                                  {item.badge}
                                </span>
                              )}
                            </>
                          )}
                        </NavLink>
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </nav>
        </div>

        {/* Footer: API & GPS Sync + Collapse Control */}
        <div className="p-3 border-t border-outline-strong shrink-0 flex flex-col gap-2">
          {(!collapsed || mobileOpen) && (
            <div className="px-3 py-2 rounded-sm bg-sidebar-hover flex items-center justify-between">
              <span className="font-label text-label-sm text-on-sidebar">API &amp; GPS Sync</span>
              <span className="inline-flex items-center gap-1 font-label text-label-sm text-on-success-container">
                <span className="w-2 h-2 rounded-full bg-success" aria-hidden="true" />
                Healthy
              </span>
            </div>
          )}

          <button
            type="button"
            onClick={onToggleCollapse}
            className="hidden lg:flex items-center justify-center gap-1.5 w-full py-1.5 rounded-sm text-on-sidebar/80 hover:text-on-sidebar hover:bg-sidebar-hover font-label text-label-sm transition-colors duration-state-change"
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? (
              <ChevronRight className="w-4 h-4" />
            ) : (
              <>
                <ChevronLeft className="w-4 h-4" />
                <span>Collapse rail</span>
              </>
            )}
          </button>
        </div>
      </aside>
    </>
  );
};
