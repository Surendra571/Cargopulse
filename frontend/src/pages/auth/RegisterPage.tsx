import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import { TruckAuthLayout } from "@/components/auth/TruckAuthLayout";
import { Alert } from "@/components/ui/alert";
import { Loader2 } from "lucide-react";

const registerSchema = z
  .object({
    first_name: z.string().min(1, "First name is required"),
    last_name: z.string().min(1, "Last name is required"),
    email: z.string().email("Please enter a valid work email address"),
    phone_code: z.string().default("+91"),
    phone_number: z.string().optional(),
    organization_name: z.string().min(2, "Organization name must be at least 2 characters"),
    org_type: z.enum(["MANUFACTURER", "CARRIER", "THIRD_PARTY_LOGISTICS", "BROKER"]),
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string().min(8, "Confirm password is required"),
    accept_terms: z.boolean().refine((val) => val === true, {
      message: "You must accept the terms of service",
    }),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type RegisterFormData = z.infer<typeof registerSchema>;

export const RegisterPage: React.FC = () => {
  const { register: registerAuth } = useAuth();
  const { addToast } = useToast();
  const navigate = useNavigate();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      phone_code: "+91",
      org_type: "MANUFACTURER",
      accept_terms: true,
    },
  });

  const onSubmit = async (data: RegisterFormData) => {
    setErrorMessage(null);
    try {
      await registerAuth({
        full_name: `${data.first_name.trim()} ${data.last_name.trim()}`,
        email: data.email,
        password: data.password,
        confirm_password: data.confirm_password,
        organization_name: data.organization_name,
        org_type: data.org_type,
        accept_terms: data.accept_terms,
      });
      navigate("/overview");
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to register organization. Please try again.");
    }
  };

  const handleSsoNotice = (provider: string) => {
    addToast({
      title: `${provider} Sign-Up Not Configured`,
      description: "Complete the organization registration form to create your workspace.",
      type: "info",
    });
  };

  return (
    <TruckAuthLayout>
      <div className="mb-5">
        <h1 className="font-headline text-headline-lg text-on-surface">
          Get started with CargoPulse
        </h1>
        <p className="text-body-sm text-on-surface-muted mt-1">
          Create your logistics workspace to manage dispatches and transporter SLAs.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-3.5" noValidate>
        {errorMessage && <Alert variant="destructive">{errorMessage}</Alert>}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="reg-first" className="block font-label text-label-md text-on-surface mb-1">
              First Name
            </label>
            <input
              id="reg-first"
              type="text"
              placeholder="Enter first name"
              {...register("first_name")}
              aria-invalid={!!errors.first_name}
              className="w-full min-h-[44px] px-3 py-2 rounded-sm bg-surface-card border border-outline-strong text-on-surface font-body text-body-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            />
            {errors.first_name && (
              <span className="font-body text-body-sm text-critical mt-0.5 block">
                {errors.first_name.message}
              </span>
            )}
          </div>
          <div>
            <label htmlFor="reg-last" className="block font-label text-label-md text-on-surface mb-1">
              Last Name
            </label>
            <input
              id="reg-last"
              type="text"
              placeholder="Enter last name"
              {...register("last_name")}
              aria-invalid={!!errors.last_name}
              className="w-full min-h-[44px] px-3 py-2 rounded-sm bg-surface-card border border-outline-strong text-on-surface font-body text-body-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            />
            {errors.last_name && (
              <span className="font-body text-body-sm text-critical mt-0.5 block">
                {errors.last_name.message}
              </span>
            )}
          </div>
        </div>

        <div>
          <label htmlFor="reg-email" className="block font-label text-label-md text-on-surface mb-1">
            Work Email
          </label>
          <input
            id="reg-email"
            type="email"
            placeholder="name@company.in"
            {...register("email")}
            aria-invalid={!!errors.email}
            className="w-full min-h-[44px] px-3.5 py-2 rounded-sm bg-surface-card border border-outline-strong text-on-surface font-body text-body-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          />
          {errors.email && (
            <span className="font-body text-body-sm text-critical mt-0.5 block">
              {errors.email.message}
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="reg-org" className="block font-label text-label-md text-on-surface mb-1">
              Company / Organization
            </label>
            <input
              id="reg-org"
              type="text"
              placeholder="Kaveri Precision Mfg"
              {...register("organization_name")}
              aria-invalid={!!errors.organization_name}
              className="w-full min-h-[44px] px-3 py-2 rounded-sm bg-surface-card border border-outline-strong text-on-surface font-body text-body-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            />
            {errors.organization_name && (
              <span className="font-body text-body-sm text-critical mt-0.5 block">
                {errors.organization_name.message}
              </span>
            )}
          </div>
          <div>
            <label htmlFor="reg-type" className="block font-label text-label-md text-on-surface mb-1">
              Organization Type
            </label>
            <select
              id="reg-type"
              {...register("org_type")}
              className="w-full min-h-[44px] px-2.5 py-2 rounded-sm bg-surface-card border border-outline-strong text-on-surface font-body text-body-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <option value="MANUFACTURER">Manufacturer</option>
              <option value="CARRIER">Transporter</option>
              <option value="THIRD_PARTY_LOGISTICS">3PL Logistics</option>
              <option value="BROKER">Freight Broker</option>
            </select>
          </div>
        </div>

        <div>
          <label htmlFor="reg-phone" className="block font-label text-label-md text-on-surface mb-1">
            Phone Number
          </label>
          <div className="flex gap-2">
            <select
              aria-label="Country code"
              {...register("phone_code")}
              className="w-24 min-h-[44px] px-2 rounded-sm bg-surface-container-low border border-outline-strong text-on-surface font-mono text-mono-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <option value="+91">+91</option>
              <option value="+61">+61</option>
              <option value="+1">+1</option>
            </select>
            <input
              id="reg-phone"
              type="tel"
              placeholder="98450 41290"
              {...register("phone_number")}
              className="flex-1 min-h-[44px] px-3.5 py-2 rounded-sm bg-surface-card border border-outline-strong text-on-surface font-mono text-mono-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label htmlFor="reg-pass" className="block font-label text-label-md text-on-surface mb-1">
              Password
            </label>
            <div className="relative">
              <input
                id="reg-pass"
                type={showPassword ? "text" : "password"}
                placeholder="Min. 8 characters"
                {...register("password")}
                aria-invalid={!!errors.password}
                className="w-full min-h-[44px] pl-3.5 pr-10 py-2 rounded-sm bg-surface-card border border-outline-strong text-on-surface font-body text-body-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              />
              <button
                type="button"
                onClick={() => setShowPassword((prev) => !prev)}
                aria-label="Show or hide password"
                className="absolute right-1.5 top-1/2 -translate-y-1/2 min-w-[32px] min-h-[32px] flex items-center justify-center text-on-surface-muted hover:text-on-surface"
              >
                <span className="material-symbols-outlined text-[18px]" aria-hidden="true">
                  {showPassword ? "visibility_off" : "visibility"}
                </span>
              </button>
            </div>
            {errors.password && (
              <span className="font-body text-body-sm text-critical mt-0.5 block">
                {errors.password.message}
              </span>
            )}
          </div>
          <div>
            <label htmlFor="reg-confirm" className="block font-label text-label-md text-on-surface mb-1">
              Confirm Password
            </label>
            <input
              id="reg-confirm"
              type={showPassword ? "text" : "password"}
              placeholder="Re-enter password"
              {...register("confirm_password")}
              aria-invalid={!!errors.confirm_password}
              className="w-full min-h-[44px] px-3.5 py-2 rounded-sm bg-surface-card border border-outline-strong text-on-surface font-body text-body-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            />
            {errors.confirm_password && (
              <span className="font-body text-body-sm text-critical mt-0.5 block">
                {errors.confirm_password.message}
              </span>
            )}
          </div>
        </div>

        <label className="inline-flex items-start gap-2 cursor-pointer">
          <input
            type="checkbox"
            {...register("accept_terms")}
            className="mt-0.5 w-4 h-4 rounded-xs border-outline-strong text-primary focus:ring-burnt-orange"
          />
          <span className="text-body-sm text-on-surface-muted">
            I accept the CargoPulse Terms of Service and GST Data Accountability Policy.
          </span>
        </label>
        {errors.accept_terms && (
          <span className="font-body text-body-sm text-critical">{errors.accept_terms.message}</span>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="mt-1 w-full min-h-[44px] px-4 py-2.5 rounded-sm bg-primary text-on-primary font-label text-label-lg hover:bg-burnt-orange focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary inline-flex items-center justify-center gap-2 disabled:opacity-60"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Creating Account...</span>
            </>
          ) : (
            <span>Create my Account</span>
          )}
        </button>

        <div className="relative flex items-center py-1.5">
          <div className="flex-grow border-t border-outline-variant" />
          <span className="px-3 text-label-sm text-on-surface-muted font-label">or sign up with</span>
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

      <div className="mt-5 pt-4 border-t border-outline-variant text-center">
        <span className="text-body-sm text-on-surface-muted">
          Already have an account?{" "}
          <Link
            to="/login"
            className="font-label text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
          >
            Login
          </Link>
        </span>
      </div>
    </TruckAuthLayout>
  );
};
