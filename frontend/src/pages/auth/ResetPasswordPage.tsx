import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { apiClient } from "@/lib/api-client";
import { AuthSplitLayout } from "@/components/auth/AuthSplitLayout";
import { Alert } from "@/components/ui/alert";
import { CheckCircle2, Loader2 } from "lucide-react";

const resetSchema = z
  .object({
    token: z.string().min(10, "A valid reset token is required"),
    new_password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string().min(8, "Confirm password is required"),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type ResetFormData = z.infer<typeof resetSchema>;

export const ResetPasswordPage: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const searchParams = new URLSearchParams(location.search);
  const initialToken = searchParams.get("token") || "";

  const [isSuccess, setIsSuccess] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetFormData>({
    resolver: zodResolver(resetSchema),
    defaultValues: {
      token: initialToken,
    },
  });

  const onSubmit = async (data: ResetFormData) => {
    setErrorMessage(null);
    try {
      await apiClient.post("/api/v1/auth/reset-password", data);
      setIsSuccess(true);
    } catch (err: any) {
      setErrorMessage(
        err.message || "Failed to reset password. The token may be expired or invalid."
      );
    }
  };

  return (
    <AuthSplitLayout>
      <div className="mb-8">
        <h1 className="font-headline text-display-lg-mobile lg:text-headline-lg text-on-surface mb-2">
          Set new password
        </h1>
        <p className="font-body text-body-md text-on-surface-muted text-pretty">
          Enter your single-use reset token and choose a new secure password.
        </p>
      </div>

      {isSuccess ? (
        <div className="space-y-4 p-6 rounded-DEFAULT bg-success-container border border-success/20 text-center">
          <div className="mx-auto h-12 w-12 rounded-full bg-surface-card border border-success/30 flex items-center justify-center text-success">
            <CheckCircle2 className="h-6 w-6" />
          </div>
          <h2 className="font-title text-title-md text-on-success-container">
            Password Reset Complete
          </h2>
          <p className="font-body text-body-sm text-on-success-container">
            Your password has been securely updated. You can now sign in using your new credentials.
          </p>
          <button
            type="button"
            onClick={() => navigate("/login")}
            className="w-full inline-flex items-center justify-center px-4 py-2.5 rounded-sm bg-primary text-on-primary font-label text-label-lg hover:bg-burnt-orange transition-colors duration-state-change"
          >
            Proceed to Sign In
          </button>
        </div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
          {errorMessage && <Alert variant="destructive">{errorMessage}</Alert>}

          <label htmlFor="token" className="flex flex-col gap-1.5">
            <span className="font-label text-label-md text-on-surface">Reset Token</span>
            <input
              id="token"
              type="text"
              placeholder="Paste your reset token here"
              {...register("token")}
              aria-invalid={!!errors.token}
              className="w-full px-3.5 py-2.5 rounded-sm bg-surface-card border border-outline-strong text-on-surface font-mono text-mono-sm placeholder:text-on-surface-subtle focus:outline-none focus:border-burnt-orange focus:ring-1 focus:ring-burnt-orange transition-colors duration-state-change"
            />
            {errors.token && (
              <span className="font-body text-body-sm text-critical">{errors.token.message}</span>
            )}
          </label>

          <label htmlFor="new_password" className="flex flex-col gap-1.5">
            <span className="font-label text-label-md text-on-surface">New Password</span>
            <input
              id="new_password"
              type="password"
              placeholder="••••••••"
              {...register("new_password")}
              aria-invalid={!!errors.new_password}
              className="w-full px-3.5 py-2.5 rounded-sm bg-surface-card border border-outline-strong text-on-surface font-body text-body-md placeholder:text-on-surface-subtle focus:outline-none focus:border-burnt-orange focus:ring-1 focus:ring-burnt-orange transition-colors duration-state-change"
            />
            {errors.new_password && (
              <span className="font-body text-body-sm text-critical">
                {errors.new_password.message}
              </span>
            )}
          </label>

          <label htmlFor="confirm_password" className="flex flex-col gap-1.5">
            <span className="font-label text-label-md text-on-surface">Confirm New Password</span>
            <input
              id="confirm_password"
              type="password"
              placeholder="••••••••"
              {...register("confirm_password")}
              aria-invalid={!!errors.confirm_password}
              className="w-full px-3.5 py-2.5 rounded-sm bg-surface-card border border-outline-strong text-on-surface font-body text-body-md placeholder:text-on-surface-subtle focus:outline-none focus:border-burnt-orange focus:ring-1 focus:ring-burnt-orange transition-colors duration-state-change"
            />
            {errors.confirm_password && (
              <span className="font-body text-body-sm text-critical">
                {errors.confirm_password.message}
              </span>
            )}
          </label>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full inline-flex items-center justify-center gap-gutter-sm px-4 py-2.5 rounded-sm bg-primary text-on-primary font-label text-label-lg hover:bg-burnt-orange transition-colors duration-state-change disabled:opacity-60"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Updating Password...</span>
              </>
            ) : (
              <span>Update Password</span>
            )}
          </button>
        </form>
      )}

      <div className="mt-6 pt-5 border-t border-outline-variant">
        <Link
          to="/login"
          className="font-label text-label-md text-primary hover:text-burnt-orange transition-colors duration-state-change"
        >
          Back to Sign In
        </Link>
      </div>
    </AuthSplitLayout>
  );
};
