type SummaryStats = {
  totalCurrent: number;
  totalPrior: number;
  totalRevised: number;
  categoryCount: number;
};

type Props = {
  stats: SummaryStats;
  year: number;
  primaryLabel: string;
  priorLabel: string | null;
};

function formatEuro(value: number): string {
  return value.toLocaleString("el-GR", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  });
}

export default function BudgetSummary({ stats, year, priorLabel }: Props) {
  const { totalCurrent, totalPrior, totalRevised, categoryCount } = stats;

  const changePct =
    priorLabel !== null && totalPrior > 0
      ? ((totalCurrent - totalPrior) / totalPrior) * 100
      : null;

  const cards = [
    {
      title: `Εγκεκριμένος Προϋπολογισμός ${year}`,
      value: formatEuro(totalCurrent),
      sub: null,
      color: "#1e40af",
    },
    priorLabel !== null
      ? {
          title: "Μεταβολή vs Προηγούμενο Έτος",
          value:
            changePct !== null
              ? `${changePct >= 0 ? "+" : ""}${changePct.toFixed(1)}%`
              : "—",
          sub: totalPrior > 0 ? `Προηγ.: ${formatEuro(totalPrior)}` : null,
          color: changePct === null ? "#64748b" : changePct >= 0 ? "#16a34a" : "#dc2626",
        }
      : {
          title: "Αριθμός Έργων",
          value: `${categoryCount}`,
          sub: "έργα",
          color: "#64748b",
        },
    {
      title: `Αναθεωρημένος ${year - 1}`,
      value: formatEuro(totalRevised),
      sub: null,
      color: "#64748b",
    },
    {
      title: "Κατηγορίες Δαπανών",
      value: `${categoryCount}`,
      sub: "κατηγορίες",
      color: "#64748b",
    },
  ];

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
        gap: "1rem",
        marginBottom: "1.5rem",
      }}
    >
      {cards.map((card) => (
        <div
          key={card.title}
          style={{
            border: "1px solid #e2e8f0",
            borderRadius: "0.5rem",
            padding: "1rem",
            background: "white",
          }}
        >
          <div
            style={{
              fontSize: "0.75rem",
              color: "#64748b",
              marginBottom: "0.25rem",
            }}
          >
            {card.title}
          </div>
          <div
            style={{
              fontSize: "1.5rem",
              fontWeight: "700",
              color: card.color,
              lineHeight: 1.2,
            }}
          >
            {card.value}
          </div>
          {card.sub && (
            <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "0.25rem" }}>
              {card.sub}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
