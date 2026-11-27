import React from "react";
import { Link } from "react-router-dom";

interface TruckAuthLayoutProps {
  children: React.ReactNode;
}

export const TruckAuthLayout: React.FC<TruckAuthLayoutProps> = ({ children }) => {
  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-surface-card text-on-surface font-body">
      {/* Left Auth Form Column */}
      <main className="bg-surface-card flex flex-col justify-between p-6 sm:p-10 lg:p-14">
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-DEFAULT bg-sidebar flex items-center justify-center border border-outline-variant shrink-0">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
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
            <div>
              <span className="font-headline text-title-md text-on-surface block leading-none">
                CargoPulse
              </span>
              <span className="font-label text-label-sm text-on-surface">
                Accountable Freight
              </span>
            </div>
          </div>

          <Link
            to="/login?options=1"
            className="font-label text-label-md text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-xs px-1"
          >
            All sign-in options
          </Link>
        </header>

        <section className="my-auto py-8 max-w-md w-full mx-auto">{children}</section>

        <footer className="flex items-center justify-between text-on-surface-subtle text-body-sm pt-4 border-t border-outline-variant">
          <span>ISO 27001 &amp; GST e-Waybill Ready</span>
          <span className="font-mono text-mono-sm">CargoPulse v2.14</span>
        </footer>
      </main>

      {/* Right Truck Hero Panel */}
      <aside
        className="hidden lg:block relative overflow-hidden bg-sidebar min-h-screen"
        aria-label="CargoPulse freight showcase"
      >
        <img
          src="/images/truck-hero.png"
          alt="CargoPulse freight truck on highway at sunset"
          className="absolute inset-0 w-full h-full object-cover object-bottom"
        />
        <div className="relative z-10 h-[46%] p-12 xl:p-16 bg-gradient-to-b from-sidebar via-sidebar/95 to-transparent flex flex-col justify-start">
          <span className="inline-flex items-center gap-2 self-start px-3 py-1 rounded-full bg-surface-card border border-outline-variant font-label text-label-sm text-on-surface mb-4">
            <span className="w-2 h-2 rounded-full bg-burnt-orange" aria-hidden="true" />
            ACCOUNTABLE FREIGHT EXECUTION
          </span>
          <h2 className="font-headline text-display-lg text-on-surface max-w-lg text-balance">
            CargoPulse — powering efficiency, one route at a time.
          </h2>
        </div>
      </aside>
    </div>
  );
};
