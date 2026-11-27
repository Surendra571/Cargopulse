import React, { useState, useRef, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { NotificationCenter } from "@/components/common/NotificationCenter";
import { User as UserIcon, LogOut, KeyRound, Settings, ShieldCheck } from "lucide-react";

interface TopBarProps {
  onOpenMobileSidebar: () => void;
  onOpenSearch: () => void;
  collapsed: boolean;
}

export const TopBar: React.FC<TopBarProps> = ({
  onOpenMobileSidebar,
  onOpenSearch,
  collapsed: _collapsed,
}) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [profileDropdownOpen, setProfileDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setProfileDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = async () => {
    setProfileDropdownOpen(false);
    await logout();
    navigate("/login");
  };

  const initials =
    `${user?.first_name?.[0] || ""}${user?.last_name?.[0] || ""}`.toUpperCase() || "CP";

  return (
    <header className="h-16 bg-surface-card border-b border-outline-variant px-3 sm:px-6 flex items-center justify-between gap-2 sm:gap-4 sticky top-0 z-30">
      {/* Mobile Nav Trigger */}
      <div className="flex items-center gap-2 lg:hidden">
        <button
          type="button"
          onClick={onOpenMobileSidebar}
          aria-label="Open navigation menu"
          className="min-w-[40px] min-h-[40px] rounded-sm bg-sidebar text-on-sidebar border border-outline-strong flex items-center justify-center hover:bg-sidebar-hover transition-colors duration-state-change"
        >
          <span className="material-symbols-outlined text-[20px]" aria-hidden="true">
            menu
          </span>
        </button>
        <span className="font-headline text-title-md text-on-surface">CargoPulse</span>
      </div>

      {/* Global Search Input Trigger */}
      <div className="hidden md:flex items-center gap-4 flex-1 max-w-xl">
        <button
          type="button"
          onClick={onOpenSearch}
          className="relative w-full flex items-center justify-between pl-9 pr-3 py-2 rounded-sm bg-surface-container-low border border-outline-variant text-on-surface-subtle font-body text-body-sm hover:border-outline-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary transition-colors duration-state-change text-left"
        >
          <span
            className="material-symbols-outlined text-[18px] text-on-surface-subtle absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
            aria-hidden="true"
          >
            search
          </span>
          <span className="truncate">Search SHP ID, transporter, vehicle reg, or city...</span>
          <span className="hidden xl:inline-flex items-center gap-1 ml-2 shrink-0">
            <kbd className="px-1.5 py-0.5 text-[10px] font-mono bg-surface-card text-on-surface-muted border border-outline-variant rounded-xs">
              Ctrl K
            </kbd>
          </span>
        </button>
      </div>

      {/* Right Utility Controls */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Mobile Search Button */}
        <button
          type="button"
          onClick={onOpenSearch}
          className="md:hidden w-9 h-9 rounded-sm border border-outline-variant bg-surface-card flex items-center justify-center text-on-surface-muted hover:bg-surface-container-low"
          aria-label="Search"
        >
          <span className="material-symbols-outlined text-[19px]" aria-hidden="true">
            search
          </span>
        </button>

        {/* Organization Selector Pill */}
        {user?.organization_name && (
          <Link
            to="/organization"
            className="hidden sm:inline-flex items-center gap-2 px-3 py-1.5 rounded-sm bg-surface-container-low border border-outline-variant text-on-surface font-label text-label-md hover:border-outline-strong transition-colors duration-state-change"
          >
            <span className="material-symbols-outlined text-[16px] text-burnt-orange" aria-hidden="true">
              factory
            </span>
            <span className="hidden md:inline truncate max-w-[200px]">
              {user.organization_name}
            </span>
            <span className="md:hidden truncate max-w-[100px]">
              {user.organization_name.split(" ")[0]}
            </span>
          </Link>
        )}

        {/* Notification Center */}
        <NotificationCenter />

        {/* Help / Health Link */}
        <Link
          to="/health"
          aria-label="System status & diagnostics"
          className="hidden sm:flex w-9 h-9 rounded-sm border border-outline-variant bg-surface-card items-center justify-center text-on-surface-muted hover:bg-surface-container-low transition-colors duration-state-change"
        >
          <span className="material-symbols-outlined text-[19px]" aria-hidden="true">
            help
          </span>
        </Link>

        {/* User Profile Dropdown */}
        <div className="relative pl-2 sm:pl-3 border-l border-outline-variant" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setProfileDropdownOpen(!profileDropdownOpen)}
            className="flex items-center gap-2.5 rounded-sm py-1 px-1.5 hover:bg-surface-container-low transition-colors duration-state-change"
            aria-expanded={profileDropdownOpen}
            aria-haspopup="true"
          >
            <div className="w-8 h-8 rounded-full bg-secondary text-on-secondary flex items-center justify-center font-label text-label-md shrink-0">
              {initials}
            </div>

            <div className="hidden xl:block text-left">
              <p className="font-label text-label-md text-on-surface leading-tight truncate max-w-[130px]">
                {user ? `${user.first_name} ${user.last_name}` : "User"}
              </p>
              <p className="font-body text-body-sm text-on-surface-subtle leading-tight truncate max-w-[130px]">
                {user?.roles?.[0] || (user?.is_superadmin ? "Super Admin" : "Operations Member")}
              </p>
            </div>

            <span
              className="material-symbols-outlined text-[16px] text-on-surface-subtle hidden sm:inline"
              aria-hidden="true"
            >
              expand_more
            </span>
          </button>

          {profileDropdownOpen && (
            <div className="absolute right-0 mt-2 w-64 bg-surface-card rounded-DEFAULT shadow-dropdown border border-outline-variant py-1.5 z-50">
              <div className="px-4 py-3 border-b border-outline-variant">
                <p className="font-label text-label-md text-on-surface">
                  {user ? `${user.first_name} ${user.last_name}` : "User"}
                </p>
                <p className="font-body text-body-sm text-on-surface-muted truncate">
                  {user?.email}
                </p>
                <div className="mt-2 flex items-center gap-1.5 flex-wrap">
                  <span className="px-2 py-0.5 rounded-full bg-primary-container text-on-primary-container font-label text-label-sm">
                    {user?.organization_name || "Enterprise"}
                  </span>
                  {user?.is_superadmin && (
                    <span className="px-2 py-0.5 rounded-full bg-warning-container text-on-warning-container font-label text-label-sm inline-flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3" /> Super Admin
                    </span>
                  )}
                </div>
              </div>

              <div className="py-1">
                <Link
                  to="/profile"
                  onClick={() => setProfileDropdownOpen(false)}
                  className="flex items-center gap-2.5 px-4 py-2 font-body text-body-sm text-on-surface hover:bg-surface-container-low transition-colors duration-state-change"
                >
                  <UserIcon className="w-4 h-4 text-on-surface-subtle" />
                  <span>My Profile</span>
                </Link>

                <Link
                  to="/change-password"
                  onClick={() => setProfileDropdownOpen(false)}
                  className="flex items-center gap-2.5 px-4 py-2 font-body text-body-sm text-on-surface hover:bg-surface-container-low transition-colors duration-state-change"
                >
                  <KeyRound className="w-4 h-4 text-on-surface-subtle" />
                  <span>Change Password</span>
                </Link>

                {(user?.is_superadmin ||
                  user?.roles?.includes("Organization Administrator") ||
                  user?.roles?.includes("ORGANIZATION_ADMIN")) && (
                  <Link
                    to="/organization"
                    onClick={() => setProfileDropdownOpen(false)}
                    className="flex items-center gap-2.5 px-4 py-2 font-body text-body-sm text-on-surface hover:bg-surface-container-low transition-colors duration-state-change"
                  >
                    <Settings className="w-4 h-4 text-on-surface-subtle" />
                    <span>Organization Settings</span>
                  </Link>
                )}
              </div>

              <div className="border-t border-outline-variant pt-1">
                <button
                  type="button"
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2.5 px-4 py-2 font-label text-label-md text-critical hover:bg-critical-container transition-colors duration-state-change text-left"
                >
                  <LogOut className="w-4 h-4 text-critical" />
                  <span>Sign Out</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
