import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  Search,
  X,
  Truck,
  Package,
  Calendar,
  AlertTriangle,
  Bot,
  FileCheck2,
  Settings,
  Users,
  ShieldCheck,
  TrendingUp,
  Radio,
  ArrowRight,
  Sparkles,
} from "lucide-react";

interface SearchItem {
  id: string;
  title: string;
  subtitle: string;
  category: "Navigation" | "Actions" | "Recent";
  icon: React.ElementType;
  path?: string;
  action?: () => void;
  badge?: string;
}

interface GlobalSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const GlobalSearchModal: React.FC<GlobalSearchModalProps> = ({ isOpen, onClose }) => {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const items: SearchItem[] = [
    // Navigation items
    {
      id: "nav-overview",
      title: "Overview Dashboard",
      subtitle: "Operational metrics, active shipments & pickup SLAs",
      category: "Navigation",
      icon: TrendingUp,
      path: "/overview",
    },
    {
      id: "nav-shipments",
      title: "Shipments Management",
      subtitle: "Freight listings, origins, destinations and delivery statuses",
      category: "Navigation",
      icon: Package,
      path: "/shipments",
    },
    {
      id: "nav-transporters",
      title: "Transporters Directory",
      subtitle: "Verified carrier network, SLAs and compliance ratings",
      category: "Navigation",
      icon: Truck,
      path: "/transporters",
    },
    {
      id: "nav-matching",
      title: "Transporter Matching",
      subtitle: "Automated route matching and carrier score ranking",
      category: "Navigation",
      icon: Sparkles,
      path: "/matching",
    },
    {
      id: "nav-bookings",
      title: "Bookings & Dispatch",
      subtitle: "Confirmed bookings, vehicle dispatches & SLA countdowns",
      category: "Navigation",
      icon: Calendar,
      path: "/bookings",
    },
    {
      id: "nav-pickup-monitoring",
      title: "Pickup Monitoring",
      subtitle: "Live gate arrival, loading milestones & pickup confirmation",
      category: "Navigation",
      icon: Radio,
      path: "/pickup-monitoring",
    },
    {
      id: "nav-exceptions",
      title: "Exceptions & Recovery",
      subtitle: "Failed pickups, delays and automated recovery workflows",
      category: "Navigation",
      icon: AlertTriangle,
      path: "/exceptions",
      badge: "3 Active",
    },
    {
      id: "nav-ai-coordinator",
      title: "AI Logistics Coordinator",
      subtitle: "Autonomous recovery decisions, proactive alerts & recommendations",
      category: "Navigation",
      icon: Bot,
      path: "/ai-coordinator",
    },
    {
      id: "nav-pod",
      title: "Proof of Delivery (POD)",
      subtitle: "Digital signature verification, consignee receipts & discrepancy checks",
      category: "Navigation",
      icon: FileCheck2,
      path: "/proof-of-delivery",
    },
    {
      id: "nav-org-settings",
      title: "Organization Settings",
      subtitle: "Company profile, addresses, operational configs & API keys",
      category: "Navigation",
      icon: Settings,
      path: "/organization",
    },
    {
      id: "nav-org-users",
      title: "Users & Team RBAC",
      subtitle: "Invite members, assign roles and manage tenant permissions",
      category: "Navigation",
      icon: Users,
      path: "/organization/users",
    },
    {
      id: "nav-audit",
      title: "Audit Trail",
      subtitle: "Immutable event logs, compliance history and tamper verification",
      category: "Navigation",
      icon: ShieldCheck,
      path: "/audit-trail",
    },
    // Quick Actions
    {
      id: "act-create-shipment",
      title: "Create New Outbound Shipment",
      subtitle: "Draft freight consignment with origin, destination & cargo specs",
      category: "Actions",
      icon: Package,
      path: "/shipments?action=create",
    },
    {
      id: "act-match-carrier",
      title: "Run Transporter Matching",
      subtitle: "Match unassigned shipments with top-performing freight partners",
      category: "Actions",
      icon: Sparkles,
      path: "/matching",
    },
    {
      id: "act-report-exception",
      title: "Log Critical Pickup Exception",
      subtitle: "Flag vehicle breakdown or driver no-show for instant recovery",
      category: "Actions",
      icon: AlertTriangle,
      path: "/exceptions?action=report",
    },
    // Recent Entities
    {
      id: "rec-shp-8921",
      title: "SHP-2026-8921 — Automotive Components (42,000 lbs)",
      subtitle: "Origin: Detroit Assembly -> Consignee: Nashville Hub (In-Transit)",
      category: "Recent",
      icon: Package,
      path: "/shipments/SHP-2026-8921",
    },
    {
      id: "rec-carrier-apex",
      title: "Apex Freight Lines (Carrier ID: CR-401)",
      subtitle: "148 active units | 99.2% on-time pickup commitment SLA",
      category: "Recent",
      icon: Truck,
      path: "/transporters/CR-401",
    },
  ];

  const filteredItems = items.filter((item) => {
    if (!query.trim()) return true;
    const q = query.toLowerCase();
    return (
      item.title.toLowerCase().includes(q) ||
      item.subtitle.toLowerCase().includes(q) ||
      item.category.toLowerCase().includes(q)
    );
  });

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  // Handle keyboard events (Escape, Enter, Up, Down)
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1 < filteredItems.length ? prev + 1 : 0));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 >= 0 ? prev - 1 : filteredItems.length - 1));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const selected = filteredItems[selectedIndex];
        if (selected) {
          if (selected.path) {
            navigate(selected.path);
          } else if (selected.action) {
            selected.action();
          }
          onClose();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, filteredItems, selectedIndex, navigate, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-24 px-4 bg-surface-card/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div
        className="w-full max-w-2xl bg-surface-card rounded-xl shadow-2xl border border-outline-variant overflow-hidden flex flex-col max-h-[80vh] animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div className="flex items-center px-4 py-3.5 border-b border-outline-variant gap-3">
          <Search className="w-5 h-5 text-on-surface-subtle shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search shipments, carriers, bookings, or jump to any module..."
            className="w-full text-sm text-on-surface placeholder:text-on-surface-subtle bg-transparent outline-none"
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              className="text-on-surface-subtle hover:text-on-surface-muted p-1 rounded-md"
            >
              <X className="w-4 h-4" />
            </button>
          )}
          <kbd className="hidden sm:inline-flex items-center gap-0.5 px-2 py-0.5 text-[11px] font-medium text-on-surface-muted bg-surface-container border border-outline-variant rounded">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div className="overflow-y-auto p-2 divide-y divide-outline-variant">
          {filteredItems.length === 0 ? (
            <div className="py-12 text-center text-on-surface-muted">
              <Search className="w-8 h-8 mx-auto text-on-surface-muted mb-2" />
              <p className="text-sm font-medium">No results found for "{query}"</p>
              <p className="text-xs text-on-surface-subtle mt-1">
                Try searching for "shipments", "transporters", "exceptions", or "matching"
              </p>
            </div>
          ) : (
            <div className="space-y-1">
              {filteredItems.map((item, idx) => {
                const Icon = item.icon;
                const isSelected = idx === selectedIndex;

                return (
                  <div
                    key={item.id}
                    onClick={() => {
                      if (item.path) navigate(item.path);
                      else if (item.action) item.action();
                      onClose();
                    }}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={`flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
                      isSelected
                        ? "bg-primary-container/80 text-blue-900"
                        : "text-on-surface hover:bg-surface-container-low"
                    }`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div
                        className={`w-8 h-8 rounded-md flex items-center justify-center shrink-0 ${
                          isSelected
                            ? "bg-primary text-white"
                            : "bg-surface-container text-on-surface-muted"
                        }`}
                      >
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold truncate">{item.title}</span>
                          {item.badge && (
                            <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 border border-amber-200">
                              {item.badge}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-on-surface-muted truncate">{item.subtitle}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0 ml-4">
                      <span className="text-[11px] font-medium text-on-surface-subtle uppercase tracking-wider">
                        {item.category}
                      </span>
                      {isSelected && <ArrowRight className="w-4 h-4 text-primary" />}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer shortcuts */}
        <div className="px-4 py-2 bg-surface-container-low border-t border-outline-variant flex items-center justify-between text-xs text-on-surface-muted">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 bg-surface-card border border-outline-variant rounded font-mono text-[10px]">
                ↑
              </kbd>
              <kbd className="px-1.5 py-0.5 bg-surface-card border border-outline-variant rounded font-mono text-[10px]">
                ↓
              </kbd>
              to navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 bg-surface-card border border-outline-variant rounded font-mono text-[10px]">
                ↵
              </kbd>
              to select
            </span>
          </div>
          <span>CargoPulse Global Command</span>
        </div>
      </div>
    </div>
  );
};
