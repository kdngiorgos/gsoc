"use client";

import { useState } from "react";
import { REVISED_LABEL, DIFF_LABEL } from "@/app/lib/labels";

export type TableItem = {
  id: number;
  code: string;
  description: string;
  parentCode: string | null;
  level: number;
  amounts: Record<string, number>;
  changePercent: number | null;
};

type Props = {
  items: TableItem[];
  year: number;
  primaryLabel: string;
  priorLabel: string | null;
};

function formatEuro(value: number | undefined): string {
  if (value == null) return "—";
  return value.toLocaleString("el-GR", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 2,
  });
}

function ChangeBadge({ pct, hasPrior }: { pct: number | null; hasPrior: boolean }) {
  if (!hasPrior) return <span style={{ color: "#94a3b8" }}>—</span>;
  if (pct === null) return <span style={{ color: "#94a3b8" }}>—</span>;
  const color = pct >= 0 ? "#16a34a" : "#dc2626";
  const bg = pct >= 0 ? "#dcfce7" : "#fee2e2";
  const sign = pct >= 0 ? "+" : "";
  return (
    <span
      style={{
        background: bg,
        color,
        borderRadius: "0.25rem",
        padding: "0.1rem 0.4rem",
        fontSize: "0.8rem",
        fontWeight: 600,
      }}
    >
      {sign}
      {pct.toFixed(1).replace(".", ",")}%
    </span>
  );
}

const INDENT_PX = [0, 16, 32, 48, 64];

export default function CollapsibleBudgetTable({ items, year, primaryLabel, priorLabel }: Props) {
  const [showDetail, setShowDetail] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const codesWithChildren = new Set(
    items.filter((i) => i.parentCode).map((i) => i.parentCode as string)
  );

  function isVisible(item: TableItem): boolean {
    if (item.level <= 1) return true;
    // Walk up to find the level-1 ancestor
    let current = item;
    while (current.level > 1) {
      const parent = items.find((i) => i.code === current.parentCode);
      if (!parent) return false;
      if (!expanded.has(parent.code)) return false;
      current = parent;
    }
    return true;
  }

  function toggleExpand(code: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(code)) {
        next.delete(code);
      } else {
        next.add(code);
      }
      return next;
    });
  }

  const th: React.CSSProperties = {
    padding: "0.5rem 0.75rem",
    borderBottom: "2px solid #cbd5e1",
    textAlign: "left",
    whiteSpace: "nowrap",
    background: "#f8fafc",
    fontSize: "0.8rem",
    color: "#475569",
  };
  const thRight: React.CSSProperties = { ...th, textAlign: "right" };
  const td: React.CSSProperties = {
    padding: "0.4rem 0.75rem",
    borderBottom: "1px solid #f1f5f9",
    fontSize: "0.875rem",
  };
  const tdRight: React.CSSProperties = { ...td, textAlign: "right" };

  const visibleItems = items.filter(isVisible);

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "0.75rem",
        }}
      >
        <h3 style={{ margin: 0, fontSize: "1rem" }}>Αναλυτικές Δαπάνες</h3>
        <button
          onClick={() => setShowDetail((v) => !v)}
          style={{
            background: "none",
            border: "1px solid #cbd5e1",
            borderRadius: "0.375rem",
            padding: "0.35rem 0.75rem",
            cursor: "pointer",
            fontSize: "0.8rem",
            color: "#475569",
          }}
        >
          {showDetail ? "Απόκρυψη λεπτομερειών ▴" : "Εμφάνιση λεπτομερειών ▾"}
        </button>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={th}>Κωδικός ΚΑΕ</th>
              <th style={th}>Περιγραφή</th>
              <th style={thRight}>
                Εγκεκριμένος Προϋπολογισμός {year}
              </th>
              <th style={thRight}>Μεταβολή</th>
              {showDetail && (
                <>
                  <th style={thRight}>Εγκεκριμένος {year - 1}</th>
                  <th style={thRight}>Αναθεωρημένος {year - 1}</th>
                  <th style={thRight}>Διαφορά (€)</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {visibleItems.map((item) => {
              const indent = INDENT_PX[Math.min(item.level, 4)];
              const hasChildren = codesWithChildren.has(item.code);
              const isOpen = expanded.has(item.code);

              return (
                <tr
                  key={item.id}
                  style={{
                    background: item.level === 0 ? "#f8fafc" : "white",
                    fontWeight: item.level <= 1 ? 600 : "normal",
                    cursor: hasChildren ? "pointer" : "default",
                  }}
                  onClick={hasChildren ? () => toggleExpand(item.code) : undefined}
                >
                  <td
                    style={{
                      ...td,
                      paddingLeft: `${indent + 8}px`,
                      fontFamily: "monospace",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {hasChildren && (
                      <span
                        style={{
                          marginRight: "0.4rem",
                          fontSize: "0.7rem",
                          color: "#64748b",
                        }}
                      >
                        {isOpen ? "▼" : "▶"}
                      </span>
                    )}
                    {item.code}
                  </td>
                  <td style={td}>{item.description}</td>
                  <td style={tdRight}>
                    {formatEuro(item.amounts[primaryLabel])}
                  </td>
                  <td style={{ ...tdRight }}>
                    <ChangeBadge pct={item.changePercent} hasPrior={priorLabel !== null} />
                  </td>
                  {showDetail && (
                    <>
                      <td style={tdRight}>
                        {priorLabel ? formatEuro(item.amounts[priorLabel]) : "—"}
                      </td>
                      <td style={tdRight}>
                        {formatEuro(item.amounts[REVISED_LABEL])}
                      </td>
                      <td style={tdRight}>
                        {formatEuro(item.amounts[DIFF_LABEL])}
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
