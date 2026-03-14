"use client";

type BarEntry = { label: string; total: number };
type Props = { data: BarEntry[] };

function formatEuro(v: number) {
  return v.toLocaleString("el-GR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
}

export default function DocumentBudgetBars({ data }: Props) {
  if (!data || data.length === 0) return null;

  const max = Math.max(...data.map((d) => d.total), 1);

  return (
    <div style={{ marginBottom: "2rem" }}>
      <h3 style={{ marginBottom: "0.75rem", fontSize: "1rem" }}>Σύγκριση Προϋπολογισμών</h3>
      {data.slice(0, 8).map((entry, i) => (
        <div key={entry.label} style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.75rem" }}>
          <span style={{ width: 24, textAlign: "right", color: "#94a3b8", fontSize: "0.8rem", flexShrink: 0 }}>
            #{i + 1}
          </span>
          <span style={{ width: 160, fontSize: "0.85rem", flexShrink: 0 }}>{entry.label}</span>
          <div style={{ flex: 1, background: "#f1f5f9", borderRadius: 4, height: 10, overflow: "hidden" }}>
            <div style={{ width: `${(entry.total / max) * 100}%`, height: "100%", background: "#1e40af", borderRadius: 4 }} />
          </div>
          <span style={{ width: 120, textAlign: "right", fontWeight: 600, fontSize: "0.85rem", flexShrink: 0 }}>
            {formatEuro(entry.total)}
          </span>
        </div>
      ))}
    </div>
  );
}
