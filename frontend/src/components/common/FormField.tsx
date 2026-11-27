import React from "react";
import { AlertCircle } from "lucide-react";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export interface FormFieldProps {
  label?: string;
  htmlFor?: string;
  required?: boolean;
  error?: string;
  hint?: string;
  children: React.ReactNode;
  className?: string;
}

export const FormField: React.FC<FormFieldProps> = ({
  label,
  htmlFor,
  required = false,
  error,
  hint,
  children,
  className,
}) => {
  return (
    <div className={cn("space-y-1.5 w-full", className)}>
      {label && (
        <div className="flex items-center justify-between">
          <Label htmlFor={htmlFor} className="text-xs font-semibold text-on-surface">
            {label}
            {required && <span className="text-rose-500 ml-1 font-bold">*</span>}
          </Label>
        </div>
      )}

      {children}

      {error ? (
        <div className="flex items-center gap-1.5 text-xs text-critical mt-1 font-medium">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          <span>{error}</span>
        </div>
      ) : hint ? (
        <p className="text-[11px] text-on-surface-muted mt-1">{hint}</p>
      ) : null}
    </div>
  );
};
