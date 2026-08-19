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
  summary_en?: string | null;
  source_lang?: string | null;
  relevance_score?: number | null;
  relevance_rationale?: string | null;
  translated?: boolean;
}

export type { NewsItemData };

const LANGUAGE_NAMES: Record<string, string> = {
  ar: "Arabic",
  fr: "French",
  pt: "Portuguese",
  es: "Spanish",
  sw: "Swahili",
  am: "Amharic",
  en: "English",
};

function ImpactBadge({ axis, level }: { axis: string; level: string }) {
  const colors: Record<string, string> = {
    H: "bg-danger/10 text-danger",
    M: "bg-amber-500/10 text-amber-400",
    L: "bg-[#21262d] text-ink-400",
  };
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-mono ${colors[level] ?? colors.L}`}>
      {axis[0].toUpperCase()}: {level}
    </span>
  );
}

function ScorerBadge({ scorer }: { scorer: string }) {
  // Any scorer that is not the keyword fallback was produced by the model.
  const isAI = scorer !== "heuristic";
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[10px] ${
        isAI ? "bg-atlas-500/15 text-atlas-400" : "bg-[#21262d] text-ink-400"
      }`}
    >
      {isAI ? "AI" : "heuristic"}
    </span>
  );
}

export default function NewsItemCard({ item }: { item: NewsItemData }) {
  return (
    <div className="rounded-[10px] border border-[#21262d] bg-[#161b22] p-3">
      <div className="flex items-start justify-between gap-2">
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-medium text-ink-100 hover:text-atlas-400"
        >
          {item.title}
        </a>
        {item.impact_score && <ScorerBadge scorer={item.impact_score.scorer} />}
      </div>
      {item.translated && item.source_lang && (
        <span className="mt-1 inline-block rounded bg-[#21262d] px-1.5 py-0.5 text-[10px] text-ink-400">
          Translated from {LANGUAGE_NAMES[item.source_lang] ?? item.source_lang}
        </span>
      )}
      <div className="mt-1 flex items-center gap-2 text-[10px] text-ink-400">
        <span>{item.source}</span>
        {item.published_at && (
          <span>{new Date(item.published_at).toLocaleDateString()}</span>
        )}
        {item.event_type && (
          <span className="rounded bg-[#21262d] px-1.5 py-0.5">{item.event_type}</span>
        )}
      </div>
      {item.relevance_rationale && (
        <p className="mt-2 text-xs leading-relaxed text-ink-400">{item.relevance_rationale}</p>
      )}
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
