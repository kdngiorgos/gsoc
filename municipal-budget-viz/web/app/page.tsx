import { prisma } from "@/lib/db";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const documents = await prisma.document.findMany({
    orderBy: { importedAt: "desc" },
    select: {
      id: true,
      filename: true,
      docType: true,
      municipality: true,
      year: true,
      importedAt: true,
      _count: { select: { budgetItems: true, projects: true } },
    },
  });

  return (
    <div>
      <h2>Imported Documents</h2>
      {documents.length === 0 ? (
        <p>No documents imported yet. Run the ETL pipeline first.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#f5f5f5" }}>
              <th style={th}>Filename</th>
              <th style={th}>Type</th>
              <th style={th}>Municipality</th>
              <th style={th}>Year</th>
              <th style={th}>Rows</th>
              <th style={th}>Imported</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => {
              const href =
                doc.docType === "BUDGET"
                  ? `/budget/${doc.id}`
                  : `/technical/${doc.id}`;
              const rowCount =
                doc.docType === "BUDGET"
                  ? doc._count.budgetItems
                  : doc._count.projects;
              return (
                <tr key={doc.id}>
                  <td style={td}>
                    <Link href={href}>{doc.filename}</Link>
                  </td>
                  <td style={td}>{doc.docType}</td>
                  <td style={td}>{doc.municipality}</td>
                  <td style={td}>{doc.year}</td>
                  <td style={td}>{rowCount}</td>
                  <td style={td}>{new Date(doc.importedAt).toLocaleDateString("el-GR")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

const th: React.CSSProperties = {
  textAlign: "left",
  padding: "0.5rem 0.75rem",
  borderBottom: "2px solid #ccc",
};
const td: React.CSSProperties = {
  padding: "0.5rem 0.75rem",
  borderBottom: "1px solid #eee",
};
