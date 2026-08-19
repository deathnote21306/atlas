import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import NewsItemCard, { type NewsItemData } from "../src/components/NewsItemCard";

const base: NewsItemData = {
  id: "1",
  url: "https://example.com/a",
  title: "IMF completes Ghana review",
  source: "reuters.com",
  published_at: "2026-08-19T10:00:00Z",
  event_type: "IMF",
  summary_en: "The board completed the review.",
  relevance_score: 88,
  relevance_rationale: "Directly changes Ghana's external financing position.",
  source_lang: "en",
  translated: false,
  impact_score: null,
};

describe("NewsItemCard", () => {
  it("shows why the item is in the feed", () => {
    render(<NewsItemCard item={base} />);
    expect(
      screen.getByText(/Directly changes Ghana's external financing position/i),
    ).toBeInTheDocument();
  });

  it("flags a translated item with its source language", () => {
    render(<NewsItemCard item={{ ...base, translated: true, source_lang: "fr" }} />);
    expect(screen.getByText(/translated from french/i)).toBeInTheDocument();
  });

  it("shows no badge for an English item", () => {
    render(<NewsItemCard item={base} />);
    expect(screen.queryByText(/translated from/i)).not.toBeInTheDocument();
  });

  it("labels an AI graded score as AI, not heuristic", () => {
    render(
      <NewsItemCard
        item={{
          ...base,
          impact_score: {
            fiscal_impact: "H",
            external_impact: "M",
            fx_impact: "L",
            political_impact: "L",
            scorer: "ai_grader",
          },
        }}
      />,
    );
    expect(screen.getByText("AI")).toBeInTheDocument();
  });
});
