import { prisma } from "@/lib/db";
import { notFound } from "next/navigation";

export const dynamic = "force-dynamic";

type Props = { params: { id: string } };

function formatAmount(value: unknown): string {
  if (value == null) return "—";
  const n = Number(value);
  return n.toLocaleString("el-GR", { minimumFractionDigits: 2 });
}

export default async function TechnicalPage({ params }: Props) {
  const docId = Number(params.id);
  const doc = await prisma.document.findUnique({ where: { id: docId } });
  if (!doc || doc.docType !== "TECHNICAL_PROGRAM") notFound();

  const projects = await prisma.technicalProject.findMany({
    where: { documentId: docId },
    include: { items: { orderBy: { id: "asc" } } },
    orderBy: [{ section: "asc" }, { id: "asc" }],
  });

  // Collect all distinct amount labels for dynamic columns
  const allLabels = Array.from(
    new Set(projects.flatMap((p) => p.items.map((i) => i.label)))
  );

  return (
    <div>
      <h2>
        {doc.filename} — {doc.municipality} {doc.year}
      </h2>
      <p style={{ color: "#666" }}>{projects.length} projects</p>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
          <thead>
            <tr style={{ background: "#f0f0f0" }}>
              <th style={th}>#</th>
              <th style={th}>Code</th>
              <th style={th}>Description</th>
              <th style={th}>Budget Ref</th>
              {allLabels.map((label) => (
                <th key={label} style={{ ...th, textAlign: "right" }}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {projects.map((project) => {
              const amountMap = Object.fromEntries(
                project.items.map((i) => [i.label, i.amount])
              );
              return (
                <tr key={project.id}>
                  <td style={{ ...td, fontFamily: "monospace", whiteSpace: "nowrap" }}>
                    {project.section}
                  </td>
                  <td style={{ ...td, fontFamily: "monospace", whiteSpace: "nowrap" }}>
                    {project.projectCode}
                  </td>
                  <td style={td}>{project.description}</td>
                  <td style={{ ...td, fontFamily: "monospace", fontSize: "0.75rem" }}>
                    {project.budgetRef ?? "—"}
                  </td>
                  {allLabels.map((label) => (
                    <td key={label} style={{ ...td, textAlign: "right" }}>
                      {formatAmount(amountMap[label])}
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
