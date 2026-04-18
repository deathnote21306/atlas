interface SynopsisData {
  id: string;
  iso3: string;
  text: string;
  key_points: { text: string; category: string }[];
  generated_at: string;
  approval_state: string;
  prompt_trace_id: string | null;
}

export type { SynopsisData };

export default function SynopsisCard({ synopsis }: { synopsis: SynopsisData | null }) {
  if (!synopsis) {
    return (
      <div className="rounded-md border border-dashed border-ink-100 bg-white p-4 text-sm text-ink-500">
        AI synopsis pending review.
      </div>
    );
  }

  return (
    <div className="rounded-md border border-ink-100 bg-white p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="rounded bg-positive/10 px-2 py-0.5 text-xs font-medium text-positive">
          {synopsis.approval_state.replace(/_/g, " ")}
        </span>
        {synopsis.prompt_trace_id && (
          <span className="text-[10px] text-ink-300" title={`Trace: ${synopsis.prompt_trace_id}`}>
            AI lineage
          </span>
        )}
      </div>
      <div className="prose prose-sm max-w-none text-ink-800">
        {synopsis.text.split("\n\n").map((p, i) => (
          <p key={i}>{p}</p>
        ))}
      </div>
      {synopsis.key_points.length > 0 && (
        <ul className="mt-3 space-y-1">
          {synopsis.key_points.map((kp, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-ink-700">
              <span className="mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-atlas-500" />
              {kp.text}
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2 text-[10px] text-ink-300">
        Generated {new Date(synopsis.generated_at).toLocaleDateString()}
      </div>
    </div>
  );
}
