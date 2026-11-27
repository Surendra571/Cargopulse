import React, { useEffect, useRef } from "react";
import { Search, X } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  autoFocus?: boolean;
  hotkeyHint?: string;
  onClear?: () => void;
}

export const SearchBar: React.FC<SearchBarProps> = ({
  value,
  onChange,
  placeholder = "Search records, IDs, or references...",
  className,
  autoFocus = false,
  hotkeyHint,
  onClear,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!hotkeyHint) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Focus when '/' is pressed and not in another input
      if (
        (e.key === "/" || (e.key === "k" && (e.metaKey || e.ctrlKey))) &&
        document.activeElement?.tagName !== "INPUT" &&
        document.activeElement?.tagName !== "TEXTAREA"
      ) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [hotkeyHint]);

  const handleClear = () => {
    onChange("");
    onClear?.();
    inputRef.current?.focus();
  };

  return (
    <div className={cn("relative flex items-center w-full", className)}>
      <Search className="absolute left-3 h-4 w-4 text-on-surface-subtle pointer-events-none" />
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoFocus={autoFocus}
        className="h-9 w-full rounded-lg border border-outline-strong bg-surface-card pl-9 pr-14 text-sm text-on-surface placeholder:text-on-surface-subtle shadow-sm transition-all focus:border-burnt-orange focus:outline-none focus:ring-2 focus:ring-burnt-orange/20"
      />
      <div className="absolute right-2.5 flex items-center gap-1.5">
        {value ? (
          <button
            type="button"
            onClick={handleClear}
            className="p-1 rounded-md text-on-surface-subtle hover:text-on-surface-muted hover:bg-surface-container transition-colors"
            title="Clear search"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        ) : hotkeyHint ? (
          <kbd className="hidden sm:inline-flex items-center rounded border border-outline-variant bg-surface-container-low px-1.5 py-0.5 text-[10px] font-medium text-on-surface-subtle font-mono shadow-xs">
            {hotkeyHint}
          </kbd>
        ) : null}
      </div>
    </div>
  );
};
