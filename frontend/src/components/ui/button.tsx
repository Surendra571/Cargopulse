import * as React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link" | "teal";
  size?: "default" | "sm" | "lg" | "icon";
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => {
    const baseStyles =
      "inline-flex items-center justify-center whitespace-nowrap rounded-sm font-label transition-colors duration-state-change focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-50 select-none";

    const variants = {
      default: "bg-primary text-on-primary hover:bg-burnt-orange",
      destructive: "bg-critical text-on-critical hover:opacity-90",
      outline: "border border-outline-strong bg-surface-card text-on-surface hover:bg-surface-container-low",
      secondary: "bg-secondary text-on-secondary hover:opacity-95",
      ghost: "text-on-surface-muted hover:bg-surface-container-low hover:text-on-surface",
      link: "text-primary underline-offset-4 hover:text-burnt-orange hover:underline",
      teal: "bg-success text-on-primary hover:opacity-95",
    };

    const sizes = {
      default: "h-9 px-4 py-2 text-label-md",
      sm: "h-8 px-3 text-label-sm",
      lg: "h-10 px-5 text-label-lg",
      icon: "h-9 w-9",
    };

    return (
      <button
        className={cn(baseStyles, variants[variant], sizes[size], className)}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button };
