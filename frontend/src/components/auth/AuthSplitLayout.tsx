import React from "react";

interface AuthSplitLayoutProps {
  children: React.ReactNode;
}

export const AuthSplitLayout: React.FC<AuthSplitLayoutProps> = ({ children }) => {
  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-12 bg-surface text-on-surface font-body">
      {/* Left Form Column */}
      <main className="lg:col-span-5 bg-surface-card flex flex-col justify-between p-5 sm:p-8 lg:p-12 lg:border-r border-outline-variant">
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
              <span className="font-label text-label-sm text-on-surface-subtle">
                B2B Logistics Operations
              </span>
            </div>
          </div>
          <span className="px-2.5 py-1 rounded-full bg-surface-container-low border border-outline-variant font-mono text-mono-sm text-on-surface-muted">
            IN-WEST / SOUTH
          </span>
        </header>

        <section className="my-auto py-8 max-w-md w-full mx-auto">{children}</section>

        <footer className="flex items-center justify-between text-on-surface-subtle pt-4 border-t border-outline-variant">
          <span className="font-body text-body-sm">ISO 27001 &amp; GST e-Waybill Ready</span>
          <span className="font-mono text-mono-sm">v2.14.0</span>
        </footer>
      </main>

      {/* Right Operational Value Panel */}
      <aside className="hidden lg:flex lg:col-span-7 bg-surface p-8 lg:p-14 flex-col justify-between">
        <div className="max-w-xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sidebar border border-outline-variant mb-6">
            <span className="w-2 h-2 rounded-full bg-burnt-orange" aria-hidden="true" />
            <span className="font-label text-label-sm text-on-sidebar">
              ACCOUNTABLE FREIGHT EXECUTION
            </span>
          </div>
          <h2 className="font-headline text-display-lg text-on-surface text-balance mb-4">
            Every shipment. Every commitment. Every update. Accountable.
          </h2>
          <p className="font-body text-body-md text-on-surface-muted text-pretty">
            CargoPulse monitors outbound plant commitments in real time, flags at-risk pickups before
            dock delays compound, and orchestrates AI-assisted transporter recovery with human
            sign-off.
          </p>
        </div>

        {/* Live Shipment Commitment Visualization */}
        <div className="my-8 bg-surface-card border border-outline-variant rounded-md p-6 max-w-xl">
          <div className="flex items-center justify-between pb-4 mb-4 border-b border-outline-variant">
            <div>
              <span className="font-label text-label-sm text-on-surface-subtle uppercase">
                Live Plant Commitment Feed
              </span>
              <p className="font-title text-title-md text-on-surface">
                Kaveri Precision Mfg — Peenya Unit II
              </p>
            </div>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-success-container text-on-success-container font-label text-label-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-success" aria-hidden="true" />
              96.4% Pickup SLA
            </span>
          </div>

          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between p-3 rounded-sm bg-surface-container-low border border-outline-variant">
              <div className="flex items-center gap-3">
                <span
                  className="material-symbols-outlined text-[20px] text-success"
                  aria-hidden="true"
                >
                  local_shipping
                </span>
                <div>
                  <p className="font-mono text-mono-sm text-on-surface">
                    SHP-2026-000125 · Bengaluru → Chennai
                  </p>
                  <p className="font-body text-body-sm text-on-surface-muted">
                    Deccan Freightlines · KA-01-MN-4829
                  </p>
                </div>
              </div>
              <span className="px-2.5 py-1 rounded-full bg-success-container text-on-success-container font-label text-label-sm">
                Confirmed
              </span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-sm bg-surface-container-low border border-outline-variant">
              <div className="flex items-center gap-3">
                <span
                  className="material-symbols-outlined text-[20px] text-warning"
                  aria-hidden="true"
                >
                  schedule
                </span>
                <div>
                  <p className="font-mono text-mono-sm text-on-surface">
                    SHP-2026-000129 · Pune → Hyderabad
                  </p>
                  <p className="font-body text-body-sm text-on-surface-muted">
                    Sahyadri Roadways · Gate check-in due in 24m
                  </p>
                </div>
              </div>
              <span className="px-2.5 py-1 rounded-full bg-warning-container text-on-warning-container font-label text-label-sm">
                Pickup at risk
              </span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-sm bg-critical-container border border-outline-variant">
              <div className="flex items-center gap-3">
                <span
                  className="material-symbols-outlined text-[20px] text-critical"
                  aria-hidden="true"
                >
                  autorenew
                </span>
                <div>
                  <p className="font-mono text-mono-sm text-on-critical-container">
                    SHP-2026-000118 · Bengaluru → Mumbai
                  </p>
                  <p className="font-body text-body-sm text-on-critical-container">
                    AI Coordinator matched 2 replacements (96% fit)
                  </p>
                </div>
              </div>
              <span className="px-2.5 py-1 rounded-full bg-surface-card text-critical font-label text-label-sm">
                Approval ready
              </span>
            </div>
          </div>
        </div>

        {/* Trust Metrics */}
        <div className="grid grid-cols-3 gap-gutter-md max-w-xl pt-4 border-t border-outline-variant">
          <div>
            <p className="font-headline text-headline-md text-on-surface tabular-nums">18 mins</p>
            <p className="font-body text-body-sm text-on-surface-muted">Median no-show recovery</p>
          </div>
          <div>
            <p className="font-headline text-headline-md text-on-surface tabular-nums">142+</p>
            <p className="font-body text-body-sm text-on-surface-muted">Verified B2B transporters</p>
          </div>
          <div>
            <p className="font-headline text-headline-md text-on-surface tabular-nums">100%</p>
            <p className="font-body text-body-sm text-on-surface-muted">Audited AI &amp; dispatch log</p>
          </div>
        </div>
      </aside>
    </div>
  );
};
