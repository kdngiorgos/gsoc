"use client";

import { COLORS } from "@/app/lib/colors";

type BarEntry = {
  name: string;
  code: string;
  current: number;
  previous: number;
};

type Props = {
  data: BarEntry[];
  insight?: string | null;
};

function formatEuro(value: number): string {
  return value.toLocaleString("el-GR", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  });
}

export default function SpendingBarChart({ data, insight }: Props) {
  if (!data || data.length === 0) return null;

  const maxCurrent = Math.max(...data.map((d) => d.current), 1);

  return (
    <div>
      <h3 style={{ marginBottom: "0.25rem", fontSize: "1rem" }}>Κατανομή Δαπανών ανά Κατηγορία</h3>
      {insight && <p style={{ fontSize: "0.8rem", color: "#64748b", margin: "0 0 0.75rem" }}>{insight}</p>}
      {data.map((entry, i) => {
        const pct = entry.previous > 0 ? ((entry.current - entry.previous) / entry.previous) * 100 : null;
        const barWidth = `${(entry.current / maxCurrent) * 100}%`;
        const color = COLORS[i % COLORS.length];
        return (
          <div key={entry.code} style={{ marginBottom: "1rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span style={{ width: 10, height: 10, borderRadius: "50%", background: color, flexShrink: 0 }} />
                <span style={{ fontSize: "0.9rem" }}>{entry.name}</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexShrink: 0 }}>
                <span style={{ fontWeight: 600 }}>{formatEuro(entry.current)}</span>
                {pct !== null && (
                  <span style={{
                    fontSize: "0.75rem",
                    padding: "2px 6px",
                    borderRadius: 9999,
                    background: pct >= 0 ? "#dcfce7" : "#fee2e2",
                    color: pct >= 0 ? "#16a34a" : "#dc2626",
                  }}>
                    {pct >= 0 ? "+" : ""}{pct.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
            <div style={{ background: "#f1f5f9", borderRadius: 4, height: 6, overflow: "hidden" }}>
              <div style={{ width: barWidth, height: "100%", background: color, borderRadius: 4 }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
