import * as React from "react";
import { cn } from "@/lib/utils";
import { AlertCircle, CheckCircle2, Info } from "lucide-react";

interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "destructive" | "success";
}

export function Alert({
  variant = "default",
  className,
  children,
  ...props
}: AlertProps) {
  const variants = {
    default: "border-outline-variant bg-primary-container text-on-primary-container",
    destructive: "border-critical/30 bg-critical-container text-on-critical-container",
    success: "border-success/30 bg-success-container text-on-success-container",
  };

  const icons = {
    default: <Info className="h-4 w-4 text-primary mt-0.5 shrink-0" />,
    destructive: <AlertCircle className="h-4 w-4 text-critical mt-0.5 shrink-0" />,
    success: <CheckCircle2 className="h-4 w-4 text-success mt-0.5 shrink-0" />,
  };

  return (
    <div
      role="alert"
      className={cn(
        "relative flex items-start gap-3 w-full rounded-sm border p-3 font-body text-body-sm",
        variants[variant],
        className
      )}
      {...props}
    >
      {icons[variant]}
      <div className="flex-1">{children}</div>
    </div>
  );
}

export function AlertDescription({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <div className={cn("text-body-sm [&_p]:leading-relaxed", className)} {...props}>
      {children}
    </div>
  );
}
