import React from "react";
import { FolderOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface EmptyStateProps {
  title?: string;
  description?: string;
  icon?: React.ReactNode;
  actionLabel?: string;
  onAction?: () => void;
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = "No records found",
  description = "No items match your query or filter criteria. Create a new record to get started.",
  icon,
  actionLabel,
  onAction,
  secondaryActionLabel,
  onSecondaryAction,
  className,
}) => {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-16 px-4 text-center bg-surface-card rounded-xl border border-dashed border-outline-variant",
        className
      )}
    >
      <div className="h-12 w-12 rounded-xl bg-surface-container-low border border-outline-variant flex items-center justify-center text-on-surface-subtle mb-4 shadow-2xs">
        {icon || <FolderOpen className="h-6 w-6 text-on-surface-subtle" />}
      </div>

      <h3 className="text-base font-semibold text-on-surface tracking-tight">{title}</h3>
      <p className="mt-1 text-xs sm:text-sm text-on-surface-muted max-w-sm leading-relaxed">{description}</p>

      {(actionLabel || secondaryActionLabel) && (
        <div className="mt-5 flex items-center gap-3">
          {actionLabel && onAction && (
            <Button
              onClick={onAction}
              size="sm"
              className="bg-primary hover:bg-burnt-orange text-white shadow-xs"
            >
              {actionLabel}
            </Button>
          )}
          {secondaryActionLabel && onSecondaryAction && (
            <Button
              variant="outline"
              size="sm"
              onClick={onSecondaryAction}
              className="text-on-surface-muted"
            >
              {secondaryActionLabel}
            </Button>
          )}
        </div>
      )}
    </div>
  );
};
