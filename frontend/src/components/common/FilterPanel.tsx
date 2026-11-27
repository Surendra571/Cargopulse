import React, { useState } from "react";
import { Filter, RotateCcw, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface FilterPanelProps {
  activeCount?: number;
  onReset?: () => void;
  onApply?: () => void;
  children: React.ReactNode;
  className?: string;
  defaultExpanded?: boolean;
}

export const FilterPanel: React.FC<FilterPanelProps> = ({
  activeCount = 0,
  onReset,
  onApply,
  children,
  className,
  defaultExpanded = false,
}) => {
  const [isOpen, setIsOpen] = useState(defaultExpanded);

  return (
    <div className={cn("rounded-xl border border-outline-variant bg-surface-card shadow-sm overflow-hidden", className)}>
      <div className="flex items-center justify-between px-4 py-3 bg-surface-container-low border-b border-outline-variant">
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-2 text-sm font-semibold text-on-surface hover:text-primary transition-colors"
        >
          <Filter className="h-4 w-4 text-primary" />
          <span>Filter Parameters</span>
          {activeCount > 0 && (
            <Badge variant="teal" className="h-5 px-1.5 text-[11px] font-bold">
              {activeCount} active
            </Badge>
          )}
          {isOpen ? (
            <ChevronUp className="h-4 w-4 text-on-surface-subtle ml-1" />
          ) : (
            <ChevronDown className="h-4 w-4 text-on-surface-subtle ml-1" />
          )}
        </button>

        <div className="flex items-center gap-2">
          {activeCount > 0 && onReset && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onReset}
              className="h-7 px-2 text-xs text-on-surface-muted hover:text-on-surface flex items-center gap-1"
            >
              <RotateCcw className="h-3 w-3" />
              Reset
            </Button>
          )}
        </div>
      </div>

      {isOpen && (
        <div className="p-4 sm:p-5 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {children}
          </div>

          <div className="flex items-center justify-end gap-2 pt-3 border-t border-outline-variant">
            {onReset && (
              <Button
                variant="outline"
                size="sm"
                onClick={onReset}
                className="text-xs text-on-surface-muted"
              >
                Clear All
              </Button>
            )}
            {onApply && (
              <Button
                variant="default"
                size="sm"
                onClick={onApply}
                className="text-xs bg-primary hover:bg-burnt-orange text-white"
              >
                Apply Filters
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
