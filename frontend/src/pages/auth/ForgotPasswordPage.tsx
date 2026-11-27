import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { apiClient } from "@/lib/api-client";
import { Alert } from "@/components/ui/alert";
import { Loader2 } from "lucide-react";

const forgotSchema = z.object({
  email: z.string().email("Please enter a valid work email address"),
});

type ForgotFormData = z.infer<typeof forgotSchema>;

export const ForgotPasswordPage: React.FC = () => {
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [submittedEmail, setSubmittedEmail] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotFormData>({
    resolver: zodResolver(forgotSchema),
  });

  const onSubmit = async (data: ForgotFormData) => {
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const res: any = await apiClient.post("/api/v1/auth/forgot-password", data);
      setSubmittedEmail(data.email);
      setSuccessMessage(
        res?.message ||
          "If this email is registered, instructions to reset your password have been sent."
      );
    } catch (err: any) {
      setErrorMessage(err.message || "Unable to process request. Please try again later.");
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-12 bg-surface text-on-surface font-body">
      {/* Left Form Column */}
      <main className="lg:col-span-5 bg-surface-card flex flex-col justify-between p-5 sm:p-8 lg:p-12 lg:border-r border-outline-variant">
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-gutter-sm">
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

          <Link
            to="/login"
            className="inline-flex items-center gap-1 font-label text-label-md text-primary hover:text-burnt-orange"
          >
            <span className="material-symbols-outlined text-[16px]" aria-hidden="true">
              arrow_back
            </span>
            <span>Back to Sign In</span>
          </Link>
        </header>

        <section className="my-auto py-8 max-w-md w-full mx-auto">
          <div className="mb-6">
            <div className="w-11 h-11 rounded-DEFAULT bg-primary-container text-on-primary-container flex items-center justify-center mb-4">
              <span className="material-symbols-outlined text-[22px]" aria-hidden="true">
                lock_reset
              </span>
            </div>
            <h1 className="font-headline text-display-lg-mobile lg:text-headline-lg text-on-surface mb-2">
              Reset your password
            </h1>
            <p className="font-body text-body-md text-on-surface-muted text-pretty">
              Enter the corporate work email linked to your CargoPulse account. We will send a
              single-use reset link valid for 15 minutes.
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-5" noValidate>
            {errorMessage && <Alert variant="destructive">{errorMessage}</Alert>}

            <label htmlFor="forgot-email" className="flex flex-col gap-1.5">
              <span className="font-label text-label-md text-on-surface">Work email</span>
              <div className="relative flex items-center">
                <span
                  aria-hidden="true"
                  className="material-symbols-outlined text-[18px] text-on-surface-subtle absolute left-3 pointer-events-none"
                >
                  mail
                </span>
                <input
                  id="forgot-email"
                  type="email"
                  placeholder="name@company.in"
                  inputMode="email"
                  {...register("email")}
                  aria-invalid={!!errors.email}
                  className="w-full pl-10 pr-3.5 py-2.5 rounded-sm bg-surface-card border border-outline-strong text-on-surface font-body text-body-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus:border-burnt-orange"
                />
              </div>
              {errors.email && (
                <span className="font-body text-body-sm text-critical">{errors.email.message}</span>
              )}
            </label>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full inline-flex items-center justify-center gap-gutter-sm px-4 py-2.5 rounded-sm bg-primary text-on-primary font-label text-label-lg hover:bg-burnt-orange focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 transition-colors duration-state-change disabled:opacity-60"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Sending Instructions...</span>
                </>
              ) : (
                <>
                  <span>Send Reset Link</span>
                  <span className="material-symbols-outlined text-[18px]" aria-hidden="true">
                    send
                  </span>
                </>
              )}
            </button>
          </form>

          {successMessage && (
            <div className="mt-6 p-4 rounded-DEFAULT bg-success-container border border-outline-variant flex items-start gap-3">
              <span
                className="material-symbols-outlined text-[20px] text-on-success-container shrink-0 mt-0.5"
                aria-hidden="true"
              >
                mark_email_read
              </span>
              <div>
                <p className="font-label text-label-md text-on-success-container">
                  Reset instructions dispatched
                </p>
                <p className="font-body text-body-sm text-on-success-container mt-0.5">
                  {submittedEmail ? (
                    <>
                      If <span className="font-mono text-mono-sm">{submittedEmail}</span> is
                      registered, check your inbox or spam folder.
                    </>
                  ) : (
                    successMessage
                  )}
                </p>
              </div>
            </div>
          )}
        </section>

        <footer className="flex items-center justify-between text-on-surface-subtle pt-4 border-t border-outline-variant">
          <span className="font-body text-body-sm">Need help? Contact IT Ops Admin</span>
          <span className="font-mono text-mono-sm">TLS 1.3</span>
        </footer>
      </main>

      {/* Right Security & Accountability Panel */}
      <aside className="hidden lg:flex lg:col-span-7 bg-surface p-8 lg:p-14 flex-col justify-between">
        <div className="max-w-xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sidebar border border-outline-variant mb-6">
            <span className="w-2 h-2 rounded-full bg-burnt-orange" aria-hidden="true" />
            <span className="font-label text-label-sm text-on-sidebar">
              ENTERPRISE ACCESS SECURITY
            </span>
          </div>
          <h2 className="font-headline text-headline-lg text-on-surface text-balance mb-3">
            Protected dispatch access with full audit accountability.
          </h2>
          <p className="font-body text-body-md text-on-surface-muted text-pretty">
            Every password reset, role change, and transporter booking approval is recorded in your
            organization&apos;s immutable audit trail.
          </p>
        </div>

        <div className="bg-surface-card border border-outline-variant rounded-md p-6 max-w-xl my-8 flex flex-col gap-4">
          <div className="flex items-center justify-between pb-3 border-b border-outline-variant">
            <span className="font-title text-title-md text-on-surface">
              Security Verification Policy
            </span>
            <span className="px-2.5 py-0.5 rounded-full bg-success-container text-on-success-container font-label text-label-sm">
              Active
            </span>
          </div>
          <div className="flex items-start gap-3">
            <span className="material-symbols-outlined text-[20px] text-burnt-orange mt-0.5" aria-hidden="true">
              timer
            </span>
            <div>
              <p className="font-label text-label-md text-on-surface">15-minute single-use token</p>
              <p className="font-body text-body-sm text-on-surface-muted">
                Reset links automatically expire after 15 minutes or upon first use.
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <span className="material-symbols-outlined text-[20px] text-burnt-orange mt-0.5" aria-hidden="true">
              devices
            </span>
            <div>
              <p className="font-label text-label-md text-on-surface">Active session revocation</p>
              <p className="font-body text-body-sm text-on-surface-muted">
                Completing a password reset signs out all other active plant workstations.
              </p>
            </div>
          </div>
        </div>

        <div className="max-w-xl pt-4 border-t border-outline-variant flex items-center justify-between text-body-sm text-on-surface-muted">
          <span>Kaveri Precision Mfg · Organization ID: ORG-BLR-019</span>
          <span className="font-mono text-mono-sm">ISO 27001</span>
        </div>
      </aside>
    </div>
  );
};
