import React, { useState, useRef, useEffect } from "react";
import { Bell, Check, Trash2, AlertTriangle, CheckCircle2, Info } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface AppNotification {
  id: string;
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
  type: "INFO" | "WARNING" | "CRITICAL" | "SUCCESS";
  link?: string;
}

const INITIAL_NOTIFICATIONS: AppNotification[] = [
  {
    id: "notif-1",
    title: "SLA Pickup Risk Detected",
    message: "Shipment #SHP-9021 carrier is 45 mins behind scheduled loading window at Pune Hub.",
    timestamp: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
    read: false,
    type: "CRITICAL",
  },
  {
    id: "notif-2",
    title: "Transporter Commitment Confirmed",
    message: "Apex Freight Lines confirmed pickup dispatch for 32FT MXL (Vehicle MH-12-QW-9921).",
    timestamp: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
    read: false,
    type: "SUCCESS",
  },
  {
    id: "notif-3",
    title: "POD Evidence Uploaded",
    message: "Driver confirmed freight delivery for Mumbai Express corridor. Signed e-POD ready for review.",
    timestamp: new Date(Date.now() - 1000 * 60 * 180).toISOString(),
    read: true,
    type: "INFO",
  },
];

export const NotificationCenter: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<AppNotification[]>(INITIAL_NOTIFICATIONS);
  const [filter, setFilter] = useState<"ALL" | "UNREAD">("ALL");
  const popoverRef = useRef<HTMLDivElement>(null);

  const unreadCount = notifications.filter((n) => !n.read).length;

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  const markAllAsRead = () => {
    setNotifications(notifications.map((n) => ({ ...n, read: true })));
  };

  const toggleRead = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setNotifications(
      notifications.map((n) => (n.id === id ? { ...n, read: !n.read } : n))
    );
  };

  const clearAll = () => {
    setNotifications([]);
  };

  const filtered = notifications.filter((n) => (filter === "UNREAD" ? !n.read : true));

  const formatRelativeTime = (isoString: string) => {
    const diffMs = Date.now() - new Date(isoString).getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${Math.floor(diffHours / 24)}d ago`;
  };

  return (
    <div className="relative" ref={popoverRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-lg text-on-surface-muted hover:text-on-surface hover:bg-surface-container transition-colors focus:outline-none"
        title="Notifications"
      >
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <span className="absolute top-1.5 right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-white shadow-xs">
            {unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-2xl border border-outline-variant bg-surface-card shadow-dropdown z-50 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
          <div className="flex items-center justify-between px-4 py-3 border-b border-outline-variant bg-surface-container-low">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm text-on-surface">Notifications</span>
              {unreadCount > 0 && (
                <Badge variant="default" className="h-4 px-1.5 text-[10px] font-bold">
                  {unreadCount} new
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-1">
              {unreadCount > 0 && (
                <button
                  onClick={markAllAsRead}
                  className="text-xs text-primary hover:text-burnt-orange hover:underline flex items-center gap-1 px-1.5 py-0.5 rounded"
                >
                  <Check className="h-3 w-3" />
                  Mark all read
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-1 px-4 py-2 border-b border-outline-variant text-xs">
            <button
              onClick={() => setFilter("ALL")}
              className={cn(
                "px-2.5 py-1 rounded-md font-medium transition-colors",
                filter === "ALL" ? "bg-surface-container text-on-surface" : "text-on-surface-muted hover:text-on-surface"
              )}
            >
              All ({notifications.length})
            </button>
            <button
              onClick={() => setFilter("UNREAD")}
              className={cn(
                "px-2.5 py-1 rounded-md font-medium transition-colors",
                filter === "UNREAD" ? "bg-surface-container text-on-surface" : "text-on-surface-muted hover:text-on-surface"
              )}
            >
              Unread ({unreadCount})
            </button>
            {notifications.length > 0 && (
              <button
                onClick={clearAll}
                className="ml-auto text-on-surface-subtle hover:text-critical p-1 rounded transition-colors"
                title="Clear all notifications"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto divide-y divide-outline-variant">
            {filtered.length === 0 ? (
              <div className="py-8 text-center text-xs text-on-surface-subtle">
                No notifications to display.
              </div>
            ) : (
              filtered.map((n) => (
                <div
                  key={n.id}
                  className={cn(
                    "p-3.5 flex items-start gap-3 hover:bg-surface-container-low transition-colors cursor-pointer",
                    !n.read && "bg-primary-container/30"
                  )}
                >
                  <div className="mt-0.5 shrink-0">
                    {n.type === "CRITICAL" && <AlertTriangle className="h-4 w-4 text-critical" />}
                    {n.type === "SUCCESS" && <CheckCircle2 className="h-4 w-4 text-success" />}
                    {n.type === "INFO" && <Info className="h-4 w-4 text-primary" />}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1">
                      <span className={cn("text-xs truncate", !n.read ? "font-bold text-on-surface" : "font-medium text-on-surface")}>
                        {n.title}
                      </span>
                      <span className="text-[10px] text-on-surface-subtle shrink-0 font-mono">
                        {formatRelativeTime(n.timestamp)}
                      </span>
                    </div>
                    <p className="text-xs text-on-surface-muted mt-0.5 line-clamp-2 leading-relaxed">
                      {n.message}
                    </p>
                  </div>

                  <button
                    onClick={(e) => toggleRead(n.id, e)}
                    className={cn(
                      "h-2 w-2 rounded-full shrink-0 mt-1.5 transition-colors",
                      !n.read ? "bg-primary hover:bg-burnt-orange" : "bg-transparent hover:bg-slate-300"
                    )}
                    title={n.read ? "Mark unread" : "Mark read"}
                  />
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};
