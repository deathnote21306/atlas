import type { ReactNode } from "react";

export interface Column<Row> {
  key: string;
  header: string;
  render?: (row: Row) => ReactNode;
  align?: "left" | "right";
}

export interface InstitutionalTableProps<Row> {
  columns: Column<Row>[];
  rows: Row[];
  emptyLabel?: string;
}

export function InstitutionalTable<Row extends object>({
  columns,
  rows,
  emptyLabel,
}: InstitutionalTableProps<Row>) {
  if (rows.length === 0 && emptyLabel) {
    return (
      <div className="rounded-md border border-ink-100 bg-white p-4 text-xs text-ink-500">
        {emptyLabel}
      </div>
    );
  }
  return (
    <div className="overflow-hidden rounded-md border border-ink-100 bg-white">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-ink-100 bg-ink-100/40 text-ink-500">
            {columns.map((c) => (
              <th
                key={c.key}
                className={`px-3 py-2 font-medium uppercase tracking-wide ${c.align === "right" ? "text-right" : "text-left"}`}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-ink-100 last:border-b-0">
              {columns.map((c) => {
                const value = c.render ? c.render(r) : (r as Record<string, ReactNode>)[c.key];
                return (
                  <td
                    key={c.key}
                    className={`px-3 py-2 font-mono text-ink-900 ${c.align === "right" ? "text-right" : "text-left"}`}
                  >
                    {value}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
