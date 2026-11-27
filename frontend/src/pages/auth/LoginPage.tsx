import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import { TruckAuthLayout } from "@/components/auth/TruckAuthLayout";
import { Alert } from "@/components/ui/alert";
import { Loader2 } from "lucide-react";

const loginSchema = z.object({
  email: z.string().email("Please enter a valid work email address"),
  password: z.string().min(1, "Password is required"),
  rememberMe: z.boolean().optional(),
});

type LoginFormData = z.infer<typeof loginSchema>;

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const { addToast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  const searchParams = new URLSearchParams(location.search);
  const redirectPath = searchParams.get("redirect") || "/overview";
  const isSessionExpired = searchParams.get("expired") === "1";
  const showOptions = searchParams.get("options") === "1";

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      rememberMe: true,
    },
  });

  const handleDemoLogin = async (email: string, password: string) => {
    setValue("email", email, { shouldValidate: true });
    setValue("password", password, { shouldValidate: true });
    setErrorMessage(null);
    try {
      await login({ email, password });
      navigate(redirectPath);
    } catch (err: any) {
      setErrorMessage(err.message || "Demo login failed. Ensure backend & seed data are running.");
    }
  };

  const onSubmit = async (data: LoginFormData) => {
    setErrorMessage(null);
    try {
      await login({ email: data.email, password: data.password });
      navigate(redirectPath);
    } catch (err: any) {
      setErrorMessage(err.message || "Invalid work email or password.");
    }
  };

  const handleSsoNotice = (provider: string) => {
    addToast({
      title: `${provider} SSO Not Configured`,
      description: "Use your corporate email/password or the Demo Workspace Access below.",
      type: "info",
    });
  };

  if (showOptions) {
    return (
      <TruckAuthLayout>
        <div className="mb-6">
          <h1 className="font-headline text-headline-lg text-on-surface">Choose how to sign in</h1>
          <p className="text-body-sm text-on-surface-muted mt-1">
            Select your organization&apos;s authentication method for CargoPulse.
          </p>
        </div>

        <div className="flex flex-col gap-3">
          <button
            type="button"
            onClick={() => handleSsoNotice("Google Workspace")}
            className="w-full min-h-[52px] px-4 py-3 rounded-sm border border-outline-strong bg-surface-card text-on-surface font-label text-label-md flex items-center justify-between gap-3 hover:bg-surface-container-low focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <span className="flex items-center gap-3">
              <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
                <path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.8-2.4 3.6v3h3.9c2.3-2.1 3.5-5.2 3.5-8.8z" />
                <path fill="#34A853" d="M12 24c3.2 0 6-1.1 8-2.9l-3.9-3c-1.1.7-2.5 1.2-4.1 1.2-3.2 0-5.9-2.1-6.9-5H1.1v3.1C3.1 21.3 7.2 24 12 24z" />
                <path fill="#FBBC05" d="M5.1 14.3c-.2-.7-.4-1.5-.4-2.3s.1-1.6.4-2.3V6.6H1.1C.4 8.2 0 10.1 0 12s.4 3.8 1.1 5.4l4-3.1z" />
                <path fill="#EA4335" d="M12 4.8c1.8 0 3.3.6 4.6 1.8l3.4-3.4C18 1.2 15.2 0 12 0 7.2 0 3.1 2.7 1.1 6.6l4 3.1c1-2.9 3.7-4.9 6.9-4.9z" />
              </svg>
              <span className="text-left">
                <span className="block font-label text-label-md text-on-surface">
                  Continue with Google Workspace
                </span>
                <span className="block text-label-sm text-on-surface-muted">
                  Sign in with your company Gmail
                </span>
              </span>
            </span>
            <span className="material-symbols-outlined text-[18px] text-on-surface-muted" aria-hidden="true">
              arrow_forward
            </span>
          </button>

          <button
            type="button"
            onClick={() => handleSsoNotice("Microsoft Entra ID")}
            className="w-full min-h-[52px] px-4 py-3 rounded-sm border border-outline-strong bg-surface-card text-on-surface font-label text-label-md flex items-center justify-between gap-3 hover:bg-surface-container-low focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <span className="flex items-center gap-3">
              <span className="material-symbols-outlined text-[20px] text-on-surface" aria-hidden="true">
                business
              </span>
              <span className="text-left">
                <span className="block font-label text-label-md text-on-surface">
                  Continue with Microsoft Entra ID
                </span>
                <span className="block text-label-sm text-on-surface-muted">
                  Corporate Azure Active Directory
                </span>
              </span>
            </span>
            <span className="material-symbols-outlined text-[18px] text-on-surface-muted" aria-hidden="true">
              arrow_forward
            </span>
          </button>

          <Link
            to="/login"
            className="w-full min-h-[52px] px-4 py-3 rounded-sm border border-outline-strong bg-surface-card text-on-surface font-label text-label-md flex items-center justify-between gap-3 hover:bg-surface-container-low focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <span className="flex items-center gap-3">
              <span className="material-symbols-outlined text-[20px] text-primary" aria-hidden="true">
                mail
              </span>
              <span className="text-left">
                <span className="block font-label text-label-md text-on-surface">
                  Work Email &amp; Password
                </span>
                <span className="block text-label-sm text-on-surface-muted">
                  Standard CargoPulse credentials
                </span>
              </span>
            </span>
            <span className="material-symbols-outlined text-[18px] text-on-surface-muted" aria-hidden="true">
              arrow_forward
            </span>
          </Link>

          <button
            type="button"
            onClick={() => handleSsoNotice("Phone Number OTP")}
            className="w-full min-h-[52px] px-4 py-3 rounded-sm border border-outline-strong bg-surface-card text-on-surface font-label text-label-md flex items-center justify-between gap-3 hover:bg-surface-container-low focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <span className="flex items-center gap-3">
              <span className="material-symbols-outlined text-[20px] text-on-surface" aria-hidden="true">
                smartphone
              </span>
              <span className="text-left">
                <span className="block font-label text-label-md text-on-surface">
                  Phone Number OTP
                </span>
                <span className="block text-label-sm text-on-surface-muted">
                  Quick access for drivers &amp; dock staff
                </span>
              </span>
            </span>
            <span className="material-symbols-outlined text-[18px] text-on-surface-muted" aria-hidden="true">
              arrow_forward
            </span>
          </button>
        </div>

        <div className="mt-6 pt-5 border-t border-outline-variant text-center">
          <span className="text-body-sm text-on-surface-muted">
            New to CargoPulse?{" "}
            <Link
              to="/register"
              className="font-label text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
            >
              Create Account
            </Link>
          </span>
        </div>
      </TruckAuthLayout>
    );
  }

  return (
    <TruckAuthLayout>
      <div className="mb-6">
        <h1 className="font-headline text-headline-lg text-on-surface">Sign in to CargoPulse</h1>
        <p className="text-body-sm text-on-surface-muted mt-1">
          Enter your work email and password to access your dispatch workspace.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
        {isSessionExpired && !errorMessage && (
          <Alert variant="destructive">
            Your session has expired. Please sign in again to continue.
          </Alert>
        )}
        {errorMessage && <Alert variant="destructive">{errorMessage}</Alert>}

        <div>
          <label htmlFor="login-email" className="block font-label text-label-md text-on-surface mb-1">
            Work Email
          </label>
          <input
            id="login-email"
            type="email"
            placeholder="name@company.in"
            inputMode="email"
            autoComplete="email"
            {...register("email")}
            aria-invalid={!!errors.email}
            className="w-full min-h-[44px] px-3.5 py-2 rounded-sm bg-surface-card border border-outline-strong text-on-surface font-body text-body-md focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          />
          {errors.email && (
            <span className="font-body text-body-sm text-critical mt-1 block">
              {errors.email.message}
            </span>
          )}
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <label htmlFor="login-pass" className="font-label text-label-md text-on-surface">
              Password
            </label>
            <Link
              to="/forgot-password"
              className="font-label text-label-sm text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
            >
              Forgot password?
            </Link>
          </div>
          <div className="relative">
            <input
              id="login-pass"
              type={showPassword ? "text" : "password"}
              placeholder="••••••••••••"
              autoComplete="current-password"
              {...register("password")}
              aria-invalid={!!errors.password}
              className="w-full min-h-[44px] pl-3.5 pr-11 py-2 rounded-sm bg-surface-card border border-outline-strong text-on-surface font-body text-body-md focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            />
            <button
              type="button"
              onClick={() => setShowPassword((prev) => !prev)}
              aria-label="Show or hide password"
              className="absolute right-1.5 top-1/2 -translate-y-1/2 min-w-[36px] min-h-[36px] flex items-center justify-center text-on-surface-muted hover:text-on-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-sm"
            >
              <span className="material-symbols-outlined text-[18px]" aria-hidden="true">
                {showPassword ? "visibility_off" : "visibility"}
              </span>
            </button>
          </div>
          {errors.password && (
            <span className="font-body text-body-sm text-critical mt-1 block">
              {errors.password.message}
            </span>
          )}
        </div>

        <label className="inline-flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            {...register("rememberMe")}
            className="w-4 h-4 rounded-xs border-outline-strong text-primary focus-visible:ring-2 focus-visible:ring-primary"
          />
          <span className="text-body-sm text-on-surface-muted">Keep me signed in for 14 days</span>
        </label>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full min-h-[44px] px-4 py-2.5 rounded-sm bg-primary text-on-primary font-label text-label-lg inline-flex items-center justify-center gap-2 hover:bg-burnt-orange focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-60"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Signing in...</span>
            </>
          ) : (
            <>
              <span>Sign in to CargoPulse</span>
              <span className="material-symbols-outlined text-[18px]" aria-hidden="true">
                arrow_forward
              </span>
            </>
          )}
        </button>

        <div className="relative flex items-center py-2">
          <div className="flex-grow border-t border-outline-variant" />
          <span className="px-3 text-label-sm text-on-surface-muted font-label">
            or continue with
          </span>
          <div className="flex-grow border-t border-outline-variant" />
        </div>

        <div className="grid grid-cols-2 gap-2.5">
          <button
            type="button"
            onClick={() => handleSsoNotice("Google")}
            className="min-h-[44px] px-3 py-2 rounded-sm border border-outline-strong bg-surface-card text-on-surface font-label text-label-md inline-flex items-center justify-center gap-2 hover:bg-surface-container-low focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
              <path
                fill="#4285F4"
                d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.8-2.4 3.6v3h3.9c2.3-2.1 3.5-5.2 3.5-8.8z"
              />
              <path
                fill="#34A853"
                d="M12 24c3.2 0 6-1.1 8-2.9l-3.9-3c-1.1.7-2.5 1.2-4.1 1.2-3.2 0-5.9-2.1-6.9-5H1.1v3.1C3.1 21.3 7.2 24 12 24z"
              />
              <path
                fill="#FBBC05"
                d="M5.1 14.3c-.2-.7-.4-1.5-.4-2.3s.1-1.6.4-2.3V6.6H1.1C.4 8.2 0 10.1 0 12s.4 3.8 1.1 5.4l4-3.1z"
              />
              <path
                fill="#EA4335"
                d="M12 4.8c1.8 0 3.3.6 4.6 1.8l3.4-3.4C18 1.2 15.2 0 12 0 7.2 0 3.1 2.7 1.1 6.6l4 3.1c1-2.9 3.7-4.9 6.9-4.9z"
              />
            </svg>
            <span>Google</span>
          </button>
          <button
            type="button"
            onClick={() => handleSsoNotice("Enterprise")}
            className="min-h-[44px] px-3 py-2 rounded-sm border border-outline-strong bg-surface-card text-on-surface font-label text-label-md inline-flex items-center justify-center gap-2 hover:bg-surface-container-low focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <span className="material-symbols-outlined text-[18px] text-primary" aria-hidden="true">
              shield
            </span>
            <span>Enterprise SSO</span>
          </button>
        </div>
      </form>

      {/* Demo Workspace Access */}
      <div className="mt-5 p-3.5 rounded-DEFAULT bg-surface-container-low border border-outline-variant space-y-2">
        <div className="flex items-center justify-between">
          <span className="font-label text-label-sm uppercase tracking-wider text-on-surface-muted">
            Demo Workspace Access (India)
          </span>
          <span className="font-mono text-[11px] text-on-surface-subtle">Seeded User</span>
        </div>
        <button
          type="button"
          onClick={() => handleDemoLogin("ananya.rao@kaverimfg.in", "Password123!")}
          disabled={isSubmitting}
          className="w-full flex items-center justify-between px-3 py-2 rounded-sm bg-surface-card border border-outline-strong hover:border-burnt-orange hover:bg-primary-container/30 transition-colors duration-state-change text-left disabled:opacity-60"
        >
          <div>
            <p className="font-label text-label-md text-on-surface">
              Ananya Rao · Kaveri Precision Mfg (Bengaluru)
            </p>
            <p className="font-mono text-mono-sm text-on-surface-muted">
              ananya.rao@kaverimfg.in / Password123!
            </p>
          </div>
          <span className="px-2 py-0.5 rounded-full bg-primary-container text-on-primary-container font-label text-label-sm">
            Use Demo
          </span>
        </button>
      </div>

      <div className="mt-5 pt-4 border-t border-outline-variant text-center">
        <span className="text-body-sm text-on-surface-muted">
          Don&apos;t have an account?{" "}
          <Link
            to="/register"
            className="font-label text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
          >
            Create Account
          </Link>
        </span>
      </div>
    </TruckAuthLayout>
  );
};
