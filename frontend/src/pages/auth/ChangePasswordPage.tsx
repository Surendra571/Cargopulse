import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { apiClient } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft, KeyRound, Loader2 } from "lucide-react";

const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, "Current password is required"),
    new_password: z.string().min(8, "New password must be at least 8 characters"),
    confirm_password: z.string().min(8, "Confirm password is required"),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "New passwords do not match",
    path: ["confirm_password"],
  })
  .refine((data) => data.current_password !== data.new_password, {
    message: "New password must be different from your current password",
    path: ["new_password"],
  });

type ChangePasswordFormData = z.infer<typeof changePasswordSchema>;

export const ChangePasswordPage: React.FC = () => {
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ChangePasswordFormData>({
    resolver: zodResolver(changePasswordSchema),
  });

  const onSubmit = async (data: ChangePasswordFormData) => {
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await apiClient.post("/api/v1/auth/change-password", data);
      setSuccessMessage("Your password has been changed successfully.");
      reset();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to change password. Please verify your current password.");
    }
  };

  return (
    <div className="max-w-xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
      <Card className="border-outline-variant bg-surface-card shadow-2xl">
        <CardHeader className="space-y-1">
          <div className="flex items-center gap-2">
            <Link
              to="/profile"
              className="p-1 rounded-md text-on-surface-subtle hover:text-white hover:bg-surface-container transition-colors"
            >
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <CardTitle className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              <KeyRound className="h-5 w-5 text-primary" />
              Change Password
            </CardTitle>
          </div>
          <CardDescription className="text-on-surface-subtle pl-7">
            Update your account password. For security, other active sessions will be terminated.
          </CardDescription>
        </CardHeader>

        <form onSubmit={handleSubmit(onSubmit)}>
          <CardContent className="space-y-4">
            {successMessage && <Alert variant="success">{successMessage}</Alert>}
            {errorMessage && <Alert variant="destructive">{errorMessage}</Alert>}

            <div className="space-y-1">
              <Label htmlFor="current_password">Current Password</Label>
              <Input
                id="current_password"
                type="password"
                placeholder="••••••••"
                {...register("current_password")}
                aria-invalid={!!errors.current_password}
              />
              {errors.current_password && (
                <p className="text-xs text-rose-400">{errors.current_password.message}</p>
              )}
            </div>

            <div className="space-y-1">
              <Label htmlFor="new_password">New Password</Label>
              <Input
                id="new_password"
                type="password"
                placeholder="••••••••"
                {...register("new_password")}
                aria-invalid={!!errors.new_password}
              />
              {errors.new_password && (
                <p className="text-xs text-rose-400">{errors.new_password.message}</p>
              )}
            </div>

            <div className="space-y-1">
              <Label htmlFor="confirm_password">Confirm New Password</Label>
              <Input
                id="confirm_password"
                type="password"
                placeholder="••••••••"
                {...register("confirm_password")}
                aria-invalid={!!errors.confirm_password}
              />
              {errors.confirm_password && (
                <p className="text-xs text-rose-400">{errors.confirm_password.message}</p>
              )}
            </div>
          </CardContent>

          <CardFooter className="flex items-center justify-between gap-4">
            <Link to="/profile">
              <Button type="button" variant="ghost" size="sm">
                Cancel
              </Button>
            </Link>

            <Button
              type="submit"
              disabled={isSubmitting}
              className="bg-primary hover:bg-burnt-orange"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save Password"
              )}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
};
