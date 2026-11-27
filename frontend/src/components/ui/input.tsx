import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-10 w-full rounded-sm border border-outline-strong bg-surface-card px-3.5 py-2 font-body text-body-md text-on-surface placeholder:text-on-surface-subtle transition-colors duration-state-change focus-visible:outline-none focus-visible:border-burnt-orange focus-visible:ring-1 focus-visible:ring-burnt-orange disabled:cursor-not-allowed disabled:bg-surface-container-low disabled:text-on-surface-muted",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export { Input };
