import React, { useState } from "react";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { LoadingState } from "./LoadingState";
import { EmptyState } from "./EmptyState";
import { Pagination, PaginationProps } from "./Pagination";
import { cn } from "@/lib/utils";

export interface ColumnDef<T> {
  id: string;
  header: string | React.ReactNode;
  cell: (row: T, index: number) => React.ReactNode;
  sortable?: boolean;
  align?: "left" | "center" | "right";
  width?: string;
  className?: string;
}

export interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[];
  keyExtractor: (row: T) => string;
  isLoading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyActionLabel?: string;
  onEmptyAction?: () => void;
  onRowClick?: (row: T) => void;
  // Selection
  selectable?: boolean;
  selectedIds?: string[];
  onSelectionChange?: (selectedIds: string[]) => void;
  // Sorting
  sortBy?: string;
  sortOrder?: "asc" | "desc";
  onSort?: (columnId: string, order: "asc" | "desc") => void;
  // Pagination
  pagination?: Omit<PaginationProps, "className">;
  className?: string;
}

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  isLoading = false,
  emptyTitle,
  emptyDescription,
  emptyActionLabel,
  onEmptyAction,
  onRowClick,
  selectable = false,
  selectedIds = [],
  onSelectionChange,
  sortBy,
  sortOrder,
  onSort,
  pagination,
  className,
}: DataTableProps<T>) {
  const [internalSortBy, setInternalSortBy] = useState<string | undefined>(sortBy);
  const [internalSortOrder, setInternalSortOrder] = useState<"asc" | "desc" | undefined>(sortOrder);

  const activeSortBy = sortBy !== undefined ? sortBy : internalSortBy;
  const activeSortOrder = sortOrder !== undefined ? sortOrder : internalSortOrder;

  const handleSortClick = (columnId: string) => {
    let nextOrder: "asc" | "desc" = "asc";
    if (activeSortBy === columnId && activeSortOrder === "asc") {
      nextOrder = "desc";
    }

    if (onSort) {
      onSort(columnId, nextOrder);
    } else {
      setInternalSortBy(columnId);
      setInternalSortOrder(nextOrder);
    }
  };

  const allSelected =
    data.length > 0 && data.every((row) => selectedIds.includes(keyExtractor(row)));

  const handleSelectAll = (checked: boolean) => {
    if (!onSelectionChange) return;
    if (checked) {
      const allIds = Array.from(new Set([...selectedIds, ...data.map(keyExtractor)]));
      onSelectionChange(allIds);
    } else {
      const pageKeys = new Set(data.map(keyExtractor));
      onSelectionChange(selectedIds.filter((id) => !pageKeys.has(id)));
    }
  };

  const handleRowSelect = (key: string, checked: boolean, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!onSelectionChange) return;
    if (checked) {
      onSelectionChange([...selectedIds, key]);
    } else {
      onSelectionChange(selectedIds.filter((id) => id !== key));
    }
  };

  return (
    <div className={cn("w-full rounded-DEFAULT border border-outline-variant bg-surface-card overflow-hidden", className)}>
      <div className="overflow-x-auto">
        <table className="w-full text-left font-body text-body-sm text-on-surface border-collapse">
          <thead className="bg-surface-container-low font-label text-label-sm uppercase tracking-wider text-on-surface-muted border-b border-outline-variant select-none">
            <tr>
              {selectable && (
                <th className="w-10 px-4 py-3 text-center">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={(e) => handleSelectAll(e.target.checked)}
                    className="h-4 w-4 rounded-xs border-outline-strong text-primary focus:ring-burnt-orange cursor-pointer"
                  />
                </th>
              )}
              {columns.map((col) => {
                const isSorted = activeSortBy === col.id;
                return (
                  <th
                    key={col.id}
                    style={{ width: col.width }}
                    className={cn(
                      "px-4 py-3.5 whitespace-nowrap",
                      col.align === "center" && "text-center",
                      col.align === "right" && "text-right",
                      col.sortable && "cursor-pointer hover:bg-surface-container transition-colors duration-state-change",
                      col.className
                    )}
                    onClick={() => col.sortable && handleSortClick(col.id)}
                  >
                    <div
                      className={cn(
                        "inline-flex items-center gap-1.5",
                        col.align === "right" && "justify-end",
                        col.align === "center" && "justify-center"
                      )}
                    >
                      <span>{col.header}</span>
                      {col.sortable && (
                        <span className="text-on-surface-subtle">
                          {isSorted ? (
                            activeSortOrder === "asc" ? (
                              <ArrowUp className="h-3.5 w-3.5 text-primary" />
                            ) : (
                              <ArrowDown className="h-3.5 w-3.5 text-primary" />
                            )
                          ) : (
                            <ArrowUpDown className="h-3 w-3 opacity-60" />
                          )}
                        </span>
                      )}
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>

          <tbody className="divide-y divide-outline-variant">
            {isLoading ? (
              <tr>
                <td colSpan={columns.length + (selectable ? 1 : 0)} className="p-0">
                  <LoadingState type="table" rows={5} columns={columns.length} />
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={columns.length + (selectable ? 1 : 0)} className="p-8">
                  <EmptyState
                    title={emptyTitle}
                    description={emptyDescription}
                    actionLabel={emptyActionLabel}
                    onAction={onEmptyAction}
                  />
                </td>
              </tr>
            ) : (
              data.map((row, index) => {
                const key = keyExtractor(row);
                const isSelected = selectedIds.includes(key);

                return (
                  <tr
                    key={key}
                    onClick={() => onRowClick?.(row)}
                    className={cn(
                      "transition-colors duration-state-change",
                      onRowClick ? "cursor-pointer hover:bg-surface-container-low" : "hover:bg-surface-container-low/70",
                      isSelected && "bg-primary-container/40"
                    )}
                  >
                    {selectable && (
                      <td className="w-10 px-4 py-3 text-center" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={(e) => handleRowSelect(key, e.target.checked, e as any)}
                          className="h-4 w-4 rounded-xs border-outline-strong text-primary focus:ring-burnt-orange cursor-pointer"
                        />
                      </td>
                    )}
                    {columns.map((col) => (
                      <td
                        key={col.id}
                        className={cn(
                          "px-4 py-3 whitespace-nowrap font-body text-body-sm text-on-surface",
                          col.align === "center" && "text-center",
                          col.align === "right" && "text-right font-mono tabular-nums",
                          col.className
                        )}
                      >
                        {col.cell(row, index)}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {pagination && <Pagination {...pagination} />}
    </div>
  );
}
