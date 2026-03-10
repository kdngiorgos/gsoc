import { prisma } from "@/lib/db";
import { notFound } from "next/navigation";
import BudgetChart from "@/app/components/BudgetChart";

export const dynamic = "force-dynamic";

type Props = { params: { id: string } };

function formatAmount(value: unknown): string {
  if (value == null) return "—";
  const n = Number(value);
  return n.toLocaleString("el-GR", { minimumFractionDigits: 2 });
}

function getLevel(code: string): number {
  if (!code.includes("-")) return 0;
  const suffix = code.split("-")[1];
  if (suffix.includes(".")) return 4;
  if (suffix.length === 4) return 3;
  if (suffix.length === 3) return 2;
  return 1;
}

const INDENT_PX = [0, 16, 32, 48, 64];

export default async function DocumentPage({ params }: Props) {
  const docId = Number(params.id);
  const doc = await prisma.document.findUnique({ where: { id: docId } });
  if (!doc) notFound();

  const items = await prisma.item.findMany({
    where: { documentId: docId },
    include: { amounts: true },
    orderBy: { id: "asc" },
  });

  // Collect all distinct amount labels (preserving insertion order)
  const labelSet = new Set<string>();
  for (const item of items) {
    for (const amt of item.amounts) {
      labelSet.add(amt.label);
    }
  }
  const labels = Array.from(labelSet);

  const isBudget = doc.docType === "BUDGET";

  // Build chart data for BUDGET docs: sum amounts labelled "ΠΥ 2025" by top-level bucket
  let chartData: { name: string; value: number }[] = [];
  if (isBudget) {
    const totals: Record<string, number> = {};
    for (const item of items) {
      const level = getLevel(item.code);
      const py2025 = item.amounts.find((a) => a.label === "ΠΥ 2025");
      if (!py2025) continue;
      const bucket = level <= 1
        ? item.description || item.code
        : item.code.split("-").slice(0, 2).join("-");
      totals[bucket] = (totals[bucket] ?? 0) + Number(py2025.amount);
    }
    chartData = Object.entries(totals)
      .map(([name, value]) => ({ name, value }))
      .filter((e) => e.value > 0)
      .sort((a, b) => b.value - a.value)
      .slice(0, 8);
  }

  const diavgeiaUrl = doc.adaCode
    ? `https://diavgeia.gov.gr/decision/view/${doc.adaCode}`
    : null;

  return (
    <div>
      <h2>
        {doc.filename} — {doc.municipality} {doc.year}
      </h2>

      {diavgeiaUrl && (
        <p style={{ marginBottom: "1rem" }}>
          <strong>Αρ. Απόφασης (ΑΔΑ):</strong>{" "}
          <a href={diavgeiaUrl} target="_blank" rel="noopener noreferrer">
            {doc.adaCode}
          </a>{" "}
          (Διαύγεια)
        </p>
      )}

      <p style={{ color: "#666" }}>{items.length} line items</p>

      {chartData.length > 0 && <BudgetChart data={chartData} />}

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
          <thead>
            <tr style={{ background: "#f0f0f0" }}>
              <th style={th}>Code</th>
              <th style={th}>Description</th>
              {labels.map((label) => (
                <th key={label} style={{ ...th, textAlign: "right" }}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const level = isBudget ? getLevel(item.code) : 0;
              const indent = INDENT_PX[level] ?? 64;
              const amountMap = Object.fromEntries(
                item.amounts.map((a) => [a.label, a.amount])
              );
              return (
                <tr
                  key={item.id}
                  style={{
                    background: level === 0 ? "#fafafa" : "white",
                    fontWeight: level <= 1 ? "600" : "normal",
                  }}
                >
                  <td
                    style={{
                      ...td,
                      paddingLeft: `${indent + 8}px`,
                      fontFamily: "monospace",
                    }}
                  >
                    {item.code}
                  </td>
                  <td style={td}>{item.description}</td>
                  {labels.map((label) => (
                    <td key={label} style={{ ...td, textAlign: "right" }}>
                      {formatAmount(amountMap[label] ?? null)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const th: React.CSSProperties = {
  padding: "0.5rem 0.75rem",
  borderBottom: "2px solid #ccc",
  textAlign: "left",
  whiteSpace: "nowrap",
};
const td: React.CSSProperties = {
  padding: "0.4rem 0.75rem",
  borderBottom: "1px solid #eee",
};
