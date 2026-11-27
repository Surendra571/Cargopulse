import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "teal" | "neutral";
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variants = {
    default: "border-transparent bg-primary-container text-on-primary-container",
    secondary: "border-transparent bg-secondary-container text-on-secondary-container",
    destructive: "border-transparent bg-critical-container text-on-critical-container",
    outline: "border-outline-strong text-on-surface bg-surface-card",
    success: "border-transparent bg-success-container text-on-success-container",
    warning: "border-transparent bg-warning-container text-on-warning-container",
    teal: "border-transparent bg-success-container text-on-success-container",
    neutral: "border-outline-variant bg-surface-container-low text-on-surface-muted",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 font-label text-label-sm transition-colors",
        variants[variant],
        className
      )}
      {...props}
    />
  );
}

export { Badge };
