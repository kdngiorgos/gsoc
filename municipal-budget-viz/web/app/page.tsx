import { prisma } from "@/lib/db";
import Link from "next/link";

export const dynamic = "force-dynamic";

type Props = {
  searchParams?: { municipality?: string };
};

export default async function HomePage({ searchParams }: Props) {
  const selectedMunicipality = searchParams?.municipality ?? "";

  // Distinct municipalities for the selector
  const municipalityRows = await prisma.document.findMany({
    select: { municipality: true },
    distinct: ["municipality"],
    orderBy: { municipality: "asc" },
  });
  const municipalities = municipalityRows.map((r) => r.municipality);

  const where = selectedMunicipality ? { municipality: selectedMunicipality } : {};

  const documents = await prisma.document.findMany({
    where,
    orderBy: { importedAt: "desc" },
    select: {
      id: true,
      filename: true,
      docType: true,
      municipality: true,
      year: true,
      adaCode: true,
      importedAt: true,
      _count: { select: { items: true } },
    },
  });

  return (
    <div>
      <h2>Imported Documents</h2>

      {/* Municipality filter */}
      <form method="get" style={{ marginBottom: "1.25rem", display: "flex", gap: "0.5rem", alignItems: "center" }}>
        <label htmlFor="municipality" style={{ fontWeight: 600 }}>
          Δήμος:
        </label>
        <select
          id="municipality"
          name="municipality"
          defaultValue={selectedMunicipality}
          style={{ padding: "0.3rem 0.5rem", fontSize: "0.9rem" }}
        >
          <option value="">— Όλοι —</option>
          {municipalities.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <button type="submit" style={{ padding: "0.3rem 0.75rem" }}>
          Φίλτρο
        </button>
        {selectedMunicipality && (
          <a href="/" style={{ fontSize: "0.85rem", color: "#666" }}>
            ✕ Καθαρισμός
          </a>
        )}
      </form>

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
              <th style={th}>ADA</th>
              <th style={th}>Imported</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => {
              const href = `/document/${doc.id}`;
              const rowCount = doc._count.items;
              return (
                <tr key={doc.id}>
                  <td style={td}>
                    <Link href={href}>{doc.filename}</Link>
                  </td>
                  <td style={td}>{doc.docType}</td>
                  <td style={td}>{doc.municipality}</td>
                  <td style={td}>{doc.year}</td>
                  <td style={td}>{rowCount}</td>
                  <td style={td}>
                    {doc.adaCode ? (
                      <a
                        href={`https://diavgeia.gov.gr/decision/view/${doc.adaCode}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ fontFamily: "monospace", fontSize: "0.8rem" }}
                      >
                        {doc.adaCode}
                      </a>
                    ) : (
                      <span style={{ color: "#bbb" }}>—</span>
                    )}
                  </td>
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
