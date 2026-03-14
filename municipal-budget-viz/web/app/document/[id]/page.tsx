import { prisma } from "@/lib/db";
import { notFound } from "next/navigation";
import Link from "next/link";
import BudgetSummary from "@/app/components/BudgetSummary";
import SpendingBarChart from "@/app/components/SpendingBarChart";
import BudgetDonutChart from "@/app/components/BudgetDonutChart";
import CollapsibleBudgetTable, { TableItem } from "@/app/components/CollapsibleBudgetTable";
import ExportCsvButton from "@/app/components/ExportCsvButton";
import { CURRENT_LABEL, PRIOR_LABEL, REVISED_LABEL } from "@/app/lib/labels";
import { kaeLabel } from "@/app/lib/kae-labels";

export const dynamic = "force-dynamic";

type Props = { params: { id: string } };

export default async function DocumentPage({ params }: Props) {
  const docId = Number(params.id);
  const doc = await prisma.document.findUnique({ where: { id: docId } });
  if (!doc) notFound();

  const items = await prisma.item.findMany({
    where: { documentId: docId },
    include: { amounts: true },
    orderBy: { id: "asc" },
  });

  const diavgeiaUrl = doc.adaCode
    ? `https://diavgeia.gov.gr/decision/view/${doc.adaCode}`
    : null;

  // ── Tree-level computation (Bug 1 fix: derive level from parentCode, not code string) ──
  const codeLevels = new Map<string, number>();
  for (const item of items) {
    if (item.parentCode === null) codeLevels.set(item.code, 0);
  }
  let changed = true;
  while (changed) {
    changed = false;
    for (const item of items) {
      if (codeLevels.has(item.code)) continue;
      const pl = item.parentCode !== null ? codeLevels.get(item.parentCode) : undefined;
      if (pl !== undefined) { codeLevels.set(item.code, pl + 1); changed = true; }
    }
  }
  for (const item of items) {
    if (!codeLevels.has(item.code)) codeLevels.set(item.code, 0);
  }

  // ── Dynamic label detection ──────────────────────────────────────────────────
  const allLabels = Array.from(new Set(items.flatMap((i) => i.amounts.map((a) => a.label))));
  const primaryLabel =
    [CURRENT_LABEL, "Προϋπολογισμός"].find((l) => allLabels.includes(l)) ??
    allLabels[0] ??
    CURRENT_LABEL;
  const priorLabel = allLabels.includes(PRIOR_LABEL) ? PRIOR_LABEL : null;
  const revisedLabel = allLabels.includes(REVISED_LABEL) ? REVISED_LABEL : null;

  // ── Build itemsWithLevel ─────────────────────────────────────────────────────
  const itemsWithLevel = items.map((item) => ({
    ...item,
    level: codeLevels.get(item.code) ?? 0,
  }));

  // ── Summary stats ─────────────────────────────────────────────────────────────
  const level0 = itemsWithLevel.filter((i) => i.level === 0);
  const summarySource = level0.length > 0 ? level0 : itemsWithLevel.filter((i) => i.level === 1);

  let totalCurrent = 0;
  let totalPrior = 0;
  let totalRevised = 0;

  for (const item of summarySource) {
    for (const amt of item.amounts) {
      const v = Number(amt.amount);
      if (amt.label === primaryLabel) totalCurrent += v;
      else if (priorLabel && amt.label === priorLabel) totalPrior += v;
      else if (revisedLabel && amt.label === revisedLabel) totalRevised += v;
    }
  }

  const level1items = itemsWithLevel.filter((i) => i.level === 1);
  const summaryStats = {
    totalCurrent,
    totalPrior,
    totalRevised,
    categoryCount: level1items.length > 0 ? level1items.length : items.length,
  };

  // ── Chart + treemap data ──────────────────────────────────────────────────────
  // Two modes:
  //  A) Proper hierarchy: level-1 items exist → use them directly
  //  B) Flat leaves: all items at level-0 but referencing un-stored parent codes
  //     → group leaves by their parentCode to create virtual chart groups

  type ChartEntry = { name: string; code: string; current: number; previous: number };
  let level1ChartData: ChartEntry[] = [];

  if (level1items.length > 0) {
    // Mode A: proper hierarchy
    level1ChartData = level1items
      .map((item) => {
        const amtMap = Object.fromEntries(item.amounts.map((a) => [a.label, Number(a.amount)]));
        return {
          name: item.description || item.code,
          code: item.code,
          current: amtMap[primaryLabel] ?? 0,
          previous: priorLabel ? (amtMap[priorLabel] ?? 0) : 0,
        };
      })
      .filter((e) => e.current > 0 || e.previous > 0)
      .sort((a, b) => b.current - a.current);
  } else {
    // Mode B: group leaf items by parentCode (virtual groups)
    const groupMap = new Map<string, { current: number; previous: number }>();

    for (const item of itemsWithLevel) {
      const key = item.parentCode ?? item.code;
      const amtMap = Object.fromEntries(item.amounts.map((a) => [a.label, Number(a.amount)]));
      const curr = amtMap[primaryLabel] ?? 0;
      const prev = priorLabel ? (amtMap[priorLabel] ?? 0) : 0;
      if (curr <= 0 && prev <= 0) continue;

      const existing = groupMap.get(key);
      if (existing) {
        existing.current += curr;
        existing.previous += prev;
      } else {
        groupMap.set(key, { current: curr, previous: prev });
      }
    }

    level1ChartData = Array.from(groupMap.entries())
      .map(([code, vals]) => ({ name: kaeLabel(code), code, current: vals.current, previous: vals.previous }))
      .filter((e) => e.current > 0 || e.previous > 0)
      .sort((a, b) => b.current - a.current);
  }

  // ── Narrative insights ────────────────────────────────────────────────────────
  let treemapInsight: string | null = null;
  let barInsight: string | null = null;

  if (level1ChartData.length > 0) {
    const topGroup = level1ChartData[0];
    const topPct = totalCurrent > 0 ? ((topGroup.current / totalCurrent) * 100).toFixed(1) : null;
    treemapInsight = topPct
      ? `Μεγαλύτερη κατηγορία: ${topGroup.name} — ${topPct}% του συνόλου`
      : null;

    const withChange = level1ChartData
      .filter((e) => e.previous > 0)
      .map((e) => ({ ...e, pct: ((e.current - e.previous) / e.previous) * 100 }));
    if (withChange.length > 0) {
      const biggest = withChange.sort((a, b) => b.pct - a.pct)[0];
      const sign = biggest.pct >= 0 ? "+" : "";
      barInsight = `Μεγαλύτερη μεταβολή: ${biggest.name} ${sign}${biggest.pct.toFixed(1)}%`;
    }
  }

  // ── Table items ───────────────────────────────────────────────────────────────
  const tableItems: TableItem[] = itemsWithLevel.map((item) => {
    const amounts = Object.fromEntries(
      item.amounts.map((a) => [a.label, Number(a.amount)])
    );
    const current = amounts[primaryLabel] ?? null;
    const prior = priorLabel ? (amounts[priorLabel] ?? null) : null;
    const changePercent =
      current !== null && prior !== null && prior !== 0
        ? ((current - prior) / prior) * 100
        : null;
    return {
      id: item.id,
      code: item.code,
      description: item.description,
      parentCode: item.parentCode,
      level: item.level,
      amounts,
      changePercent,
    };
  });

  return (
    <div>
      <Link href="/" style={btnOutline}>← Back to Documents</Link>
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

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <p style={{ color: "#666", margin: 0 }}>{items.length} line items</p>
        <ExportCsvButton
          items={tableItems}
          primaryLabel={primaryLabel}
          priorLabel={priorLabel}
          filename={`${doc.municipality}_${doc.year}_budget.csv`}
        />
      </div>

      <BudgetSummary
        stats={summaryStats}
        year={doc.year}
        primaryLabel={primaryLabel}
        priorLabel={priorLabel}
      />

      {level1ChartData.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "2rem", marginBottom: "2rem" }}>
          <BudgetDonutChart data={level1ChartData} totalCurrent={totalCurrent} insight={treemapInsight} />
          <SpendingBarChart data={level1ChartData} insight={barInsight} />
        </div>
      )}

      <CollapsibleBudgetTable
        items={tableItems}
        year={doc.year}
        primaryLabel={primaryLabel}
        priorLabel={priorLabel}
      />
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
  marginBottom: "0.75rem",
};
