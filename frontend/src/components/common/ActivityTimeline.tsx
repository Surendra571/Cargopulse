import React from "react";
import { cn } from "@/lib/utils";

export interface TimelineEvent {
  id: string;
  title: string;
  description?: string | null;
  timestamp: string;
  actor?: string | null;
  iconColor?: "emerald" | "teal" | "blue" | "amber" | "rose" | "slate";
}

interface ActivityTimelineProps {
  events: TimelineEvent[];
  className?: string;
}

const dotColorMap: Record<string, string> = {
  emerald: "bg-success border-success-container",
  teal: "bg-success border-success-container",
  blue: "bg-primary border-primary-container",
  amber: "bg-warning border-warning-container",
  rose: "bg-critical border-critical-container",
  slate: "bg-on-surface-subtle border-surface-container",
};

export const ActivityTimeline: React.FC<ActivityTimelineProps> = ({
  events,
  className,
}) => {
  if (!events || events.length === 0) {
    return (
      <p className="font-body text-body-sm text-on-surface-subtle py-4 text-center">
        No activity events recorded yet.
      </p>
    );
  }

  return (
    <ol className={cn("relative border-l border-outline-variant ml-2.5 space-y-5", className)}>
      {events.map((event) => {
        const dotClass = dotColorMap[event.iconColor || "blue"] || dotColorMap.blue;
        return (
          <li key={event.id} className="ml-5 relative">
            <span
              className={cn(
                "absolute -left-[27px] top-1 w-3 h-3 rounded-full border-2",
                dotClass
              )}
              aria-hidden="true"
            />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="font-label text-label-md text-on-surface">{event.title}</h4>
              <time className="font-mono text-mono-sm text-on-surface-subtle tabular-nums">
                {new Date(event.timestamp).toLocaleString()}
              </time>
            </div>
            {event.description && (
              <p className="font-body text-body-sm text-on-surface-muted mt-0.5">
                {event.description}
              </p>
            )}
            {event.actor && (
              <p className="font-label text-label-sm text-on-surface-subtle mt-1">
                Actor: {event.actor}
              </p>
            )}
          </li>
        );
      })}
    </ol>
  );
};
