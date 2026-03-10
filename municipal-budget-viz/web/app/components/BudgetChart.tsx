"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

type ChartEntry = {
  name: string;
  value: number;
};

type Props = {
  data: ChartEntry[];
};

const COLORS = [
  "#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed",
  "#0891b2", "#be185d", "#059669", "#b45309", "#6d28d9",
];

function formatEuro(value: number): string {
  return value.toLocaleString("el-GR", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  });
}

export default function BudgetChart({ data }: Props) {
  if (!data || data.length === 0) return null;

  return (
    <div style={{ width: "100%", height: 380, marginBottom: "2rem" }}>
      <h3 style={{ marginBottom: "0.5rem", fontSize: "1rem" }}>
        Κατανομή Δαπανών 2025 ανά KAE (κορυφαίες κατηγορίες)
      </h3>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius={130}
            label={({ name, percent }) =>
              `${name} (${(percent * 100).toFixed(1)}%)`
            }
            labelLine={false}
          >
            {data.map((_, index) => (
              <Cell
                key={`cell-${index}`}
                fill={COLORS[index % COLORS.length]}
              />
            ))}
          </Pie>
          <Tooltip formatter={(value: number) => formatEuro(value)} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
