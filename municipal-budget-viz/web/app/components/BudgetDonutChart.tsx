"use client";

import { PieChart, Pie, Cell, Tooltip } from "recharts";
import { COLORS } from "@/app/lib/colors";

type Props = {
  data: { name: string; code: string; current: number }[];
  totalCurrent: number;
  insight?: string | null;
};

function formatEuro(v: number) {
  return v.toLocaleString("el-GR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
}

export default function BudgetDonutChart({ data, totalCurrent, insight }: Props) {
  if (!data || data.length === 0) return null;

  const sorted = [...data].sort((a, b) => b.current - a.current);
  const top5 = sorted.slice(0, 5);
  const rest = sorted.slice(5);
  const restTotal = rest.reduce((s, e) => s + e.current, 0);

  const slices = restTotal > 0
    ? [...top5, { name: "Λοιπές κατηγορίες", code: "", current: restTotal }]
    : top5;

  return (
    <div>
      <h3 style={{ marginBottom: "0.25rem", fontSize: "1rem" }}>Κατανομή Προϋπολογισμού</h3>
      {insight && <p style={{ fontSize: "0.8rem", color: "#64748b", margin: "0 0 0.75rem" }}>{insight}</p>}
      <div style={{ display: "flex", gap: "2rem", flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ position: "relative", width: 260, height: 260, flexShrink: 0 }}>
          <PieChart width={260} height={260}>
            <Pie
              data={slices}
              dataKey="current"
              nameKey="name"
              innerRadius={70}
              outerRadius={115}
              paddingAngle={2}
            >
              {slices.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const s = payload[0].payload as { name: string; code: string; current: number };
                const pct = totalCurrent > 0 ? ((s.current / totalCurrent) * 100).toFixed(1) : "0.0";
                return (
                  <div style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: 6, padding: "0.5rem 0.75rem", fontSize: "0.85rem", maxWidth: 260 }}>
                    <div style={{ fontWeight: 600, marginBottom: 4 }}>{s.name}</div>
                    {s.code && <div style={{ fontSize: "0.75rem", color: "#64748b", marginBottom: 4 }}>KAE: {s.code}</div>}
                    <div>{formatEuro(s.current)} ({pct}%)</div>
                  </div>
                );
              }}
            />
          </PieChart>
          <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", pointerEvents: "none" }}>
            <span style={{ fontSize: "0.75rem", color: "#64748b" }}>Σύνολο</span>
            <span style={{ fontSize: "1.1rem", fontWeight: 700 }}>{formatEuro(totalCurrent)}</span>
          </div>
        </div>
        <ul style={{ listStyle: "none", padding: 0, margin: 0, flex: 1, alignSelf: "center" }}>
          {slices.map((s, i) => (
            <li key={s.name} style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
              <span style={{ width: 12, height: 12, borderRadius: "50%", background: COLORS[i % COLORS.length], flexShrink: 0 }} />
              <span style={{ flex: 1, fontSize: "0.875rem" }}>{s.name}</span>
              <span style={{ fontWeight: 600, fontSize: "0.875rem" }}>{formatEuro(s.current)}</span>
              <span style={{ color: "#64748b", fontSize: "0.8rem", minWidth: 40, textAlign: "right" }}>
                {totalCurrent > 0 ? ((s.current / totalCurrent) * 100).toFixed(1) : "0.0"}%
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
