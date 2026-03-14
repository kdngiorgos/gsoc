import { prisma } from "@/lib/db";
import Link from "next/link";
import { CURRENT_LABEL } from "@/app/lib/labels";
import DocumentBudgetBars from "@/app/components/DocumentBudgetBars";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 20;

type Props = {
  searchParams?: { municipality?: string; q?: string; page?: string };
};

export default async function HomePage({ searchParams }: Props) {
  const selectedMunicipality = searchParams?.municipality ?? "";
  const searchQuery = searchParams?.q?.trim() ?? "";
  const page = Math.max(1, parseInt(searchParams?.page ?? "1", 10) || 1);

  // Distinct municipalities for the selector
  const municipalityRows = await prisma.document.findMany({
    select: { municipality: true },
    distinct: ["municipality"],
    orderBy: { municipality: "asc" },
  });
  const municipalities = municipalityRows.map((r) => r.municipality);

  const [totalBudgetResult, budgetMuniRows, totalDocCount, yearRange, docBudgets] = await Promise.all([
    prisma.itemAmount.aggregate({
      _sum: { amount: true },
      where: {
        label: CURRENT_LABEL,
        item: { parentCode: null },
      },
    }),
    prisma.document.findMany({
      select: { municipality: true },
      distinct: ["municipality"],
    }),
    prisma.document.count(),
    prisma.document.aggregate({ _min: { year: true }, _max: { year: true } }),
    prisma.document.findMany({
      select: {
        id: true,
        municipality: true,
        year: true,
        // No parentCode filter: only leaf items are stored in current ETL output
        items: {
          select: { amounts: { where: { label: CURRENT_LABEL }, select: { amount: true } } },
        },
      },
    }),
  ]);
  const totalBudget = Number(totalBudgetResult._sum.amount ?? 0);
  const comparisonData = docBudgets
    .map((d) => ({
      label: `${d.municipality} ${d.year}`,
      total: d.items.reduce(
        (s, i) => s + i.amounts.reduce((sa, a) => sa + Number(a.amount), 0),
        0
      ),
    }))
    .filter((d) => d.total > 0)
    .sort((a, b) => b.total - a.total);
  const budgetMunicipalityCount = budgetMuniRows.length;
  const yearMin = yearRange._min.year;
  const yearMax = yearRange._max.year;
  const yearDisplay = yearMin && yearMax
    ? yearMin === yearMax ? String(yearMin) : `${yearMin} – ${yearMax}`
    : "—";

  // --- Search mode ---
  const searchResults = searchQuery
    ? await prisma.item.findMany({
        where: {
          description: { contains: searchQuery, mode: "insensitive" },
          ...(selectedMunicipality
            ? { document: { municipality: selectedMunicipality } }
            : {}),
        },
        include: {
          document: {
            select: { id: true, filename: true, municipality: true, year: true },
          },
        },
        orderBy: { id: "asc" },
        take: 100,
      })
    : null;

  // --- Document list mode ---
  const where = selectedMunicipality ? { municipality: selectedMunicipality } : {};
  const [documents, docTotal] = searchResults
    ? [[], 0]
    : await Promise.all([
        prisma.document.findMany({
          where,
          orderBy: { importedAt: "desc" },
          skip: (page - 1) * PAGE_SIZE,
          take: PAGE_SIZE,
          select: {
            id: true,
            filename: true,
            municipality: true,
            year: true,
            adaCode: true,
            importedAt: true,
            _count: { select: { items: true } },
          },
        }),
        prisma.document.count({ where }),
      ]);
  const totalPages = Math.max(1, Math.ceil(docTotal / PAGE_SIZE));

  return (
    <div>
      <h2>Imported Documents</h2>

      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
        gap: "1rem",
        marginBottom: "1.5rem",
      }}>
        {[
          {
            title: "Συνολικός Προϋπολογισμός",
            value: totalBudget.toLocaleString("el-GR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }),
            color: "#1e40af",
          },
          {
            title: "Σύνολο Εγγράφων",
            value: `${totalDocCount} έγγραφα`,
            color: "#7c3aed",
          },
          {
            title: "Δήμοι με Προϋπολογισμό",
            value: `${budgetMunicipalityCount} δήμοι`,
            color: "#0891b2",
          },
          {
            title: "Έτη",
            value: yearDisplay,
            color: "#b45309",
          },
        ].map((card) => (
          <div key={card.title} style={{ border: "1px solid #e2e8f0", borderRadius: "0.5rem", padding: "1rem", background: "white" }}>
            <div style={{ fontSize: "0.75rem", color: "#64748b", marginBottom: "0.25rem" }}>{card.title}</div>
            <div style={{ fontSize: "1.5rem", fontWeight: 700, color: card.color }}>{card.value}</div>
          </div>
        ))}
      </div>

      {comparisonData.length > 0 && (
        <DocumentBudgetBars data={comparisonData} />
      )}

      {/* Filters */}
      <form
        method="get"
        style={{ marginBottom: "1.25rem", display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}
      >
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

        <label htmlFor="q" style={{ fontWeight: 600, marginLeft: "0.5rem" }}>
          Αναζήτηση:
        </label>
        <input
          id="q"
          name="q"
          type="search"
          defaultValue={searchQuery}
          placeholder="Αναζήτηση κωδικού ή περιγραφής…"
          style={{ padding: "0.3rem 0.5rem", fontSize: "0.9rem", minWidth: "220px" }}
        />

        <input type="hidden" name="page" value="1" />
        <button type="submit" style={btnPrimary}>
          Εφαρμογή
        </button>
        {(selectedMunicipality || searchQuery) && (
          <a href="/" style={{ fontSize: "0.85rem", color: "#9f1239", cursor: "pointer", textDecoration: "none" }}>
            ✕ Καθαρισμός
          </a>
        )}
      </form>

      {/* Search results */}
      {searchResults && (
        <>
          <p style={{ color: "#666", marginBottom: "0.75rem" }}>
            {searchResults.length === 100
              ? "Εμφάνιση πρώτων 100 αποτελεσμάτων"
              : `${searchResults.length} αποτελέσματα`}{" "}
            για &ldquo;{searchQuery}&rdquo;
          </p>
          {searchResults.length === 0 ? (
            <p>Δεν βρέθηκαν αποτελέσματα.</p>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "#f5f5f5" }}>
                  <th style={th}>Κωδικός</th>
                  <th style={th}>Περιγραφή</th>
                  <th style={th}>Δήμος</th>
                  <th style={th}>Έτος</th>
                  <th style={th}>Έγγραφο</th>
                </tr>
              </thead>
              <tbody>
                {searchResults.map((item) => (
                  <tr key={item.id}>
                    <td style={{ ...td, fontFamily: "monospace" }}>{item.code}</td>
                    <td style={td}>{item.description}</td>
                    <td style={td}>{item.document.municipality}</td>
                    <td style={td}>{item.document.year}</td>
                    <td style={td}>
                      <Link href={`/document/${item.document.id}`}>{item.document.filename}</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}

      {/* Document list */}
      {!searchResults && (
        <>
          {documents.length === 0 ? (
            <p>No documents imported yet. Run the ETL pipeline first.</p>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "#f5f5f5" }}>
                  <th style={th}>Filename</th>
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
          {totalPages > 1 && (
            <div style={{ display: "flex", gap: "1rem", alignItems: "center", justifyContent: "center", marginTop: "1rem", fontSize: "0.9rem" }}>
              {page > 1 ? (
                <Link href={`/?${new URLSearchParams({ ...(selectedMunicipality ? { municipality: selectedMunicipality } : {}), page: String(page - 1) })}`} style={btnOutline}>
                  ← Προηγούμενη
                </Link>
              ) : (
                <span style={btnDisabled}>← Προηγούμενη</span>
              )}
              <span style={{ color: "#64748b" }}>Σελίδα {page} / {totalPages}</span>
              {page < totalPages ? (
                <Link href={`/?${new URLSearchParams({ ...(selectedMunicipality ? { municipality: selectedMunicipality } : {}), page: String(page + 1) })}`} style={btnOutline}>
                  Επόμενη →
                </Link>
              ) : (
                <span style={btnDisabled}>Επόμενη →</span>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

const btnOutline: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "0.35rem 0.75rem",
  border: "1px solid #cbd5e1",
  borderRadius: "0.375rem",
  fontSize: "0.875rem",
  color: "#374151",
  textDecoration: "none",
  background: "white",
  cursor: "pointer",
};
const btnDisabled: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "0.35rem 0.75rem",
  border: "1px solid #cbd5e1",
  borderRadius: "0.375rem",
  fontSize: "0.875rem",
  color: "#cbd5e1",
  textDecoration: "none",
  background: "white",
  cursor: "default",
  pointerEvents: "none",
};
const btnPrimary: React.CSSProperties = {
  background: "#1e40af",
  color: "white",
  border: "none",
  borderRadius: "0.375rem",
  padding: "0.35rem 0.875rem",
  cursor: "pointer",
  fontSize: "0.875rem",
  fontWeight: 600,
};
const th: React.CSSProperties = {
  textAlign: "left",
  padding: "0.5rem 0.75rem",
  borderBottom: "2px solid #ccc",
};
const td: React.CSSProperties = {
  padding: "0.5rem 0.75rem",
  borderBottom: "1px solid #eee",
};
