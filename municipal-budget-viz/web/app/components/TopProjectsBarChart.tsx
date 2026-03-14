"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import type { TableItem } from "@/app/components/CollapsibleBudgetTable";

type Props = { items: TableItem[]; primaryLabel: string };

function formatEuro(v: number) {
  return v.toLocaleString("el-GR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
}

export default function TopProjectsBarChart({ items, primaryLabel }: Props) {
  const sorted = [...items]
    .filter((i) => (i.amounts[primaryLabel] ?? 0) > 0)
    .sort((a, b) => (b.amounts[primaryLabel] ?? 0) - (a.amounts[primaryLabel] ?? 0))
    .slice(0, 15);

  if (sorted.length === 0) return null;

  const chartData = sorted.map((i) => ({
    name: (i.description || i.code).length > 40
      ? (i.description || i.code).slice(0, 40) + "…"
      : (i.description || i.code),
    fullName: i.description || i.code,
    value: i.amounts[primaryLabel] ?? 0,
  }));

  const height = 300 + sorted.length * 40;

  return (
    <div style={{ width: "100%", height, marginBottom: "2rem" }}>
      <h3 style={{ marginBottom: "0.5rem", fontSize: "1rem" }}>
        Κορυφαία Έργα ανά Προϋπολογισμό
      </h3>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          layout="vertical"
          data={chartData}
          margin={{ top: 4, right: 32, left: 8, bottom: 4 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <YAxis
            type="category"
            dataKey="name"
            width={220}
            tick={{ fontSize: 11 }}
          />
          <XAxis
            type="number"
            tickFormatter={(v: number) => `${(v / 1_000_000).toFixed(1)}M€`}
            tick={{ fontSize: 11 }}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const entry = payload[0].payload as typeof chartData[0];
              return (
                <div style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: 6, padding: "0.5rem 0.75rem", fontSize: "0.85rem" }}>
                  <div style={{ fontWeight: 600, marginBottom: 2 }}>{entry.fullName}</div>
                  <div>{formatEuro(entry.value)}</div>
                </div>
              );
            }}
          />
          <Bar dataKey="value" name="Προϋπολογισμός" fill="#2563eb" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
