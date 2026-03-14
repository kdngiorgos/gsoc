"use client";

import { TableItem } from "@/app/components/CollapsibleBudgetTable";
import { REVISED_LABEL, DIFF_LABEL } from "@/app/lib/labels";

type Props = {
  items: TableItem[];
  primaryLabel: string;
  priorLabel: string | null;
  filename: string;
};

function escapeCsv(value: string | number | null | undefined): string {
  if (value == null) return "";
  const str = String(value);
  if (str.includes(",") || str.includes('"') || str.includes("\n")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

export default function ExportCsvButton({ items, primaryLabel, priorLabel, filename }: Props) {
  function handleExport() {

    const allLabels = Array.from(new Set(items.flatMap((i) => Object.keys(i.amounts))));
    const hasRevised = allLabels.includes(REVISED_LABEL);
    const hasDiff = allLabels.includes(DIFF_LABEL);

    const headers = [
      "Κωδικός ΚΑΕ",
      "Περιγραφή",
      "Επίπεδο",
      primaryLabel,
      ...(priorLabel ? [priorLabel] : []),
      "Μεταβολή %",
      ...(hasRevised ? [REVISED_LABEL] : []),
      ...(hasDiff ? [DIFF_LABEL] : []),
    ];

    const rows = items.map((item) => [
      escapeCsv(item.code),
      escapeCsv(item.description),
      escapeCsv(item.level),
      escapeCsv(item.amounts[primaryLabel] ?? ""),
      ...(priorLabel ? [escapeCsv(item.amounts[priorLabel] ?? "")] : []),
      escapeCsv(item.changePercent != null ? item.changePercent.toFixed(2) : ""),
      ...(hasRevised ? [escapeCsv(item.amounts[REVISED_LABEL] ?? "")] : []),
      ...(hasDiff ? [escapeCsv(item.amounts[DIFF_LABEL] ?? "")] : []),
    ]);

    const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const bom = "\uFEFF"; // UTF-8 BOM for Excel
    const blob = new Blob([bom + csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <button
      onClick={handleExport}
      style={{
        background: "#1e40af",
        color: "white",
        border: "none",
        borderRadius: "0.375rem",
        padding: "0.4rem 0.875rem",
        cursor: "pointer",
        fontSize: "0.85rem",
        fontWeight: 600,
      }}
    >
      Εξαγωγή CSV ↓
    </button>
  );
}
