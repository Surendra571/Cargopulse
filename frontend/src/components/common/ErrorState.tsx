import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = "Failed to load operational data",
  message = "An unexpected error occurred while communicating with the CargoPulse server. Please check your network or try again.",
  onRetry,
  className,
}) => {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-14 px-4 text-center bg-surface-card rounded-xl border border-rose-200/80 shadow-xs",
        className
      )}
    >
      <div className="h-12 w-12 rounded-xl bg-critical-container border border-rose-200 flex items-center justify-center text-critical mb-3 shadow-2xs">
        <AlertTriangle className="h-6 w-6" />
      </div>

      <h3 className="text-base font-semibold text-on-surface tracking-tight">{title}</h3>
      <p className="mt-1 text-xs sm:text-sm text-on-surface-muted max-w-md leading-relaxed">{message}</p>

      {onRetry && (
        <Button
          onClick={onRetry}
          size="sm"
          variant="outline"
          className="mt-5 border-outline-strong text-on-surface hover:bg-surface-container-low flex items-center gap-1.5 shadow-2xs"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Try Again</span>
        </Button>
      )}
    </div>
  );
};
