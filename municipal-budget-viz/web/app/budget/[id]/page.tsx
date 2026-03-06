import { prisma } from "@/lib/db";
import { notFound } from "next/navigation";

export const dynamic = "force-dynamic";

type Props = { params: { id: string } };

function formatAmount(value: unknown): string {
  if (value == null) return "—";
  const n = Number(value);
  return n.toLocaleString("el-GR", { minimumFractionDigits: 2 });
}

const INDENT_PX = [0, 16, 32, 48, 64];

export default async function BudgetPage({ params }: Props) {
  const docId = Number(params.id);
  const doc = await prisma.document.findUnique({ where: { id: docId } });
  if (!doc || doc.docType !== "BUDGET") notFound();

  const items = await prisma.budgetItem.findMany({
    where: { documentId: docId },
    include: { category: true },
    orderBy: { id: "asc" },
  });

  return (
    <div>
      <h2>
        {doc.filename} — {doc.municipality} {doc.year}
      </h2>
      <p style={{ color: "#666" }}>{items.length} line items</p>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
          <thead>
            <tr style={{ background: "#f0f0f0" }}>
              <th style={th}>KAE Code</th>
              <th style={th}>Description</th>
              <th style={{ ...th, textAlign: "right" }}>2024</th>
              <th style={{ ...th, textAlign: "right" }}>Mid-year</th>
              <th style={{ ...th, textAlign: "right" }}>2025</th>
              <th style={{ ...th, textAlign: "right" }}>Variance</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const indent = INDENT_PX[item.category.level] ?? 64;
              return (
                <tr
                  key={item.id}
                  style={{
                    background: item.category.level === 0 ? "#fafafa" : "white",
                    fontWeight: item.category.level <= 1 ? "600" : "normal",
                  }}
                >
                  <td style={{ ...td, paddingLeft: `${indent + 8}px`, fontFamily: "monospace" }}>
                    {item.category.code}
                  </td>
                  <td style={td}>{item.description || item.category.description}</td>
                  <td style={{ ...td, textAlign: "right" }}>{formatAmount(item.amount2024)}</td>
                  <td style={{ ...td, textAlign: "right" }}>{formatAmount(item.amountMidYear)}</td>
                  <td style={{ ...td, textAlign: "right" }}>{formatAmount(item.amount2025)}</td>
                  <td style={{ ...td, textAlign: "right" }}>{formatAmount(item.amountVariance)}</td>
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
