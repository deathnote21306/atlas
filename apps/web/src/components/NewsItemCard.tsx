interface ImpactScore {
  fiscal_impact: string;
  external_impact: string;
  fx_impact: string;
  political_impact: string;
  scorer: string;
}

interface NewsItemData {
  id: string;
  title: string;
  url: string;
  source: string;
  published_at: string | null;
  event_type: string | null;
  impact_score: ImpactScore | null;
}

export type { NewsItemData };

function ImpactBadge({ axis, level }: { axis: string; level: string }) {
  const colors: Record<string, string> = {
    H: "bg-danger/10 text-danger",
    M: "bg-amber-100 text-amber-700",
    L: "bg-ink-100 text-ink-500",
  };
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-mono ${colors[level] ?? colors.L}`}>
      {axis[0].toUpperCase()}: {level}
    </span>
  );
}

function ScorerBadge({ scorer }: { scorer: string }) {
  const isAI = scorer.startsWith("claude");
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[10px] ${
        isAI ? "bg-atlas-100 text-atlas-700" : "bg-ink-100 text-ink-500"
      }`}
    >
      {isAI ? "AI" : "heuristic"}
    </span>
  );
}

export default function NewsItemCard({ item }: { item: NewsItemData }) {
  return (
    <div className="rounded-md border border-ink-100 bg-white p-3">
      <div className="flex items-start justify-between gap-2">
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-medium text-ink-800 hover:text-atlas-600"
        >
          {item.title}
        </a>
        {item.impact_score && <ScorerBadge scorer={item.impact_score.scorer} />}
      </div>
      <div className="mt-1 flex items-center gap-2 text-[10px] text-ink-400">
        <span>{item.source}</span>
        {item.published_at && (
          <span>{new Date(item.published_at).toLocaleDateString()}</span>
        )}
        {item.event_type && (
          <span className="rounded bg-ink-100 px-1.5 py-0.5">{item.event_type}</span>
        )}
      </div>
      {item.impact_score && (
        <div className="mt-2 flex flex-wrap gap-1">
          <ImpactBadge axis="fiscal" level={item.impact_score.fiscal_impact} />
          <ImpactBadge axis="external" level={item.impact_score.external_impact} />
          <ImpactBadge axis="fx" level={item.impact_score.fx_impact} />
          <ImpactBadge axis="political" level={item.impact_score.political_impact} />
        </div>
      )}
    </div>
  );
}
