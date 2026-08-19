# News Relevance and Quality Rework

**Date:** 2026-08-19
**Status:** Approved design, ready for planning
**Area:** `apps/api/src/atlas_api/services/news/`

## Problem

Review of the live app surfaced three defects in the country news feeds:

1. **Irrelevant articles.** Items appear that have nothing to do with sovereign risk (sport, crime, celebrity coverage).
2. **Non-English articles.** Arabic and French items are served raw, mainly on EGY, MAR and CIV.
3. **Wrong country attribution.** Articles appear under a country that is only mentioned in passing rather than the country the article is about.

### Root causes (traced in code, 2026-08-19)

| Defect | Cause |
|---|---|
| Irrelevant | `gdelt.py:COUNTRY_QUERIES` queries the bare country name with no topic terms, so GDELT returns all coverage. The only gate is `nlp.py:is_relevant`, which passes an article on **2 keyword matches** from a broad list containing common words such as "trade" and "investment". |
| Non-English | `poll_gdelt` has an `english_only` flag defaulting to `False`, and `pipeline.py` calls it without setting it. No language detection exists anywhere. |
| Wrong country | `nlp.py:extract_country` returns the **first** matching country entity, then falls back to substring matching any country name anywhere in the text. A passing mention wins. |

## Goals

- Country feeds contain only sovereign macro news and politics that is material to sovereign risk.
- Every served item is readable in English, with non-English sources preserved rather than discarded.
- Every item is filed under the country it is actually about.
- Volume stays healthy. Cleaning the feed must not empty it.
- Every item can explain why it was included.

### Non-goals

- No change to the risk scoring model, synopses, or any non-news surface.
- No new frontend routes. The existing News tab and `GET /api/news` shape are extended, not replaced.
- No paid news API. Sources stay free (GDELT plus RSS).

## Editorial policy

**In scope:** sovereign debt, IMF programmes, rating actions, fiscal and monetary policy, FX, reserves, bonds and eurobonds, growth, inflation, material trade and investment flows, plus **politics that materially affects creditworthiness** (elections, coups, sanctions, major reform, significant unrest).

**Out of scope:** sport, entertainment, crime blotter, general human interest, routine corporate news with no sovereign read-through, and politics with no plausible link to creditworthiness.

## Architecture

```
poll sources -> normalize -> cheap pre-filters -> AI grader -> persist -> serve
                (lang detect,   (dedup, junk cut,  (1 structured
                 candidate iso3) budget cap)        call per article)
```

Deterministic stages cut volume cheaply. The AI stage makes the judgement calls that keywords cannot. Four units, each independently testable.

### Unit 1: `sources.py` (extends `gdelt.py`, `rss.py`)

**Purpose:** produce raw candidate articles.

- GDELT queries gain topic terms so junk is cut at the source. Each country query becomes the country name ANDed with a macro and politics theme clause, for example `Ghana AND (debt OR IMF OR inflation OR bond OR fiscal OR "central bank" OR rating OR election OR sanctions)`.
- `english_only` stays `False` on purpose. Non-English items are wanted, and language is handled downstream.
- `max_records` raised from 50 to 100 per country to protect volume.
- RSS feed list expanded with reputable English pan-African macro and finance feeds. The current single Reuters Africa feed is the main volume constraint.

**Depends on:** `httpx`. **Output:** `list[RawArticle]`.

### Unit 2: `prefilter.py` (new)

**Purpose:** reduce the set that reaches the AI, without making editorial judgements.

- **Language detection.** Detect source language, store it, and never drop on this basis.
- **Hard junk cut.** A deliberately narrow blocklist for obviously off-topic content (sport, entertainment, obituaries). Narrow by design so it cannot silently eat macro news.
- **Candidate country guess.** Reuse the existing NER to propose a candidate, used only for prompt context. Final attribution belongs to the AI.
- **Existing dedup retained.** URL hash dedup and pgvector semantic dedup (cosine > 0.92) run before the AI so duplicates are never paid for.
- **Budget cap.** At most `NEWS_AI_CALLS_PER_RUN` items proceed per run. Items over the cap persist with `ai_graded = false` and are picked up by the next run. Nothing is lost.

**Depends on:** language detector, existing `dedup.py` and `semantic_dedup.py`, `nlp.py`. **Output:** ordered candidate list plus deferred remainder.

### Unit 3: `ai_grader.py` (new)

**Purpose:** one structured Claude call per candidate that decides relevance, attribution, translation, classification and impact together. Judging these jointly is both cheaper and more accurate than separate calls, because they share the same reading of the article.

Reuses `services/ai/provider.py:call_tool` and `persist_trace`, matching the existing `news_scorer.py` pattern.

Result model:

| Field | Type | Purpose |
|---|---|---|
| `relevant` | bool | primary gate |
| `relevance_score` | int 0-100 | ranking and the volume dial |
| `rationale` | str, one sentence | shown in the UI and auditable |
| `primary_iso3` | str or null | true subject country, restricted to the 10 tracked countries |
| `secondary_iso3` | list[str] | other genuinely covered countries |
| `event_type` | existing `EventType` enum | reuses current taxonomy |
| `fiscal_impact`, `external_impact`, `fx_impact`, `political_impact` | existing `ImpactLevel` enum | populates `NewsImpactScore` |
| `source_lang` | ISO 639-1 | provenance label |
| `title_en`, `summary_en` | str | translation when non-English, faithful pass-through when English |

**Keep rule:** `relevant` is true AND `relevance_score >= NEWS_RELEVANCE_THRESHOLD` AND `primary_iso3` is one of the 10 tracked countries.

The system prompt states the editorial policy above verbatim, instructs that a country mentioned only in passing must not be returned as `primary_iso3`, and requires a rationale grounded in the article text.

**Depends on:** `provider.py`, `atlas_schemas.news`. **Output:** validated result or `None`.

### Unit 4: `persist.py` (extends `pipeline.py`)

Writes the graded item, its country links, its impact score and its prompt trace in one transaction.

## Data model

Migration `0017_news_relevance`.

**`news_item` gains:**

| Column | Type | Notes |
|---|---|---|
| `source_lang` | `String(8)` nullable | detected language |
| `original_title` | `Text` nullable | pre-translation title, retained for provenance |
| `summary_en` | `Text` nullable | English summary served in the feed |
| `relevant` | `Boolean` not null default `false` | serving gate. Nothing is served until something has judged it |
| `relevance_score` | `Integer` nullable | ranking and threshold |
| `relevance_rationale` | `Text` nullable | why this item is here |
| `ai_graded` | `Boolean` not null default `false` | false means heuristic or deferred |
| `prompt_trace_id` | `UUID` FK nullable | lineage, matching the synopsis pattern |

`title` continues to hold the served (English) title so existing readers keep working. `original_title` holds the source text when a translation occurred.

**New table `news_item_country`:** `(news_item_id, iso3, role)` where `role` is `primary` or `secondary`, primary key `(news_item_id, iso3)`. This lets one article legitimately appear on two country feeds, which raises volume honestly rather than by loosening standards. `news_item.primary_iso3` is retained and kept in sync so nothing that reads it today breaks.

## API and serving

`GET /api/news` keeps its path and shape, extended additively:

- Only items with `relevant = true` are served. `relevant` defaults to `false` and is set by a judgement: the AI grader when it runs, or the heuristic fallback during an AI outage. Items still deferred over the budget cap stay withheld until a later run grades them. Rejected items stay withheld permanently.

  This default is what clears the existing junk. The migration lands `relevant = false` on every current row, so the defective items stop being served immediately, and the backfill then restores the good ones. The feed is therefore thin between the migration and the end of the backfill, so the two run back to back during deployment.
- Filtering by `iso3` matches against `news_item_country` (primary or secondary) instead of only `primary_iso3`.
- Ordering becomes `relevance_score DESC, published_at DESC`, so the strongest items lead.
- `NewsItemOut` gains `summary_en`, `source_lang`, `relevance_score`, `relevance_rationale`, and `translated` (true when `original_title` is set). All optional, so existing clients are unaffected.
- The News tab renders the rationale under each headline and a "Translated from Arabic" style badge when `translated` is true, with the original-language link preserved.

## Volume protection

The relevance bar rises, so volume is protected deliberately:

1. Wider intake (more RSS feeds, `max_records` 50 to 100).
2. Non-English items retained through translation rather than dropped, which matters most for EGY, MAR and CIV.
3. Secondary-country links surface one article on every country it genuinely covers.
4. `NEWS_RELEVANCE_THRESHOLD` (default 60) is a single env dial. Lower it for more coverage, raise it for a stricter feed. Nothing is hard-dropped by keyword, so tuning never requires a code change.

**Acceptance target:** after the backfill, every one of the 10 countries has at least 5 relevant items, and no country feed is empty. If a country falls short at threshold 60, lower the threshold rather than widening the editorial policy.

## Backfill and cleanup

The defective items are already in the production database, so future-only fixes would leave the demo dirty. A one-off script `apps/api/scripts/regrade_news.py` re-runs existing `news_item` rows through the new grader:

- Items failing the keep rule are marked `relevant = false` and stop being served. They are **not** hard deleted, so the decision is reversible and auditable.
- Items passing are updated with score, rationale, correct attribution and translation.
- Runs in batches with the same token budget guard as `daily_rescore.py`, and is safe to re-run.

## Configuration

| Setting | Default | Purpose |
|---|---|---|
| `NEWS_RELEVANCE_THRESHOLD` | 60 | keep bar and volume dial |
| `NEWS_AI_CALLS_PER_RUN` | 40 | per-run cost cap |
| `NEWS_TRANSLATE_ENABLED` | true | kill switch for translation |
| `news_poll_enabled` | unchanged (`false`) | existing flag, enabled separately when the feed is trusted |

The existing 200k daily token cap in `provider.py` remains the outer bound.

## Error handling

| Failure | Behaviour |
|---|---|
| AI call fails or returns invalid data | Fall back to improved heuristic (tighter keyword set, primary-subject country attribution). Item persists with `ai_graded = false`, so the nightly job re-grades it later. |
| Daily token cap hit | Stop grading, persist remaining items as deferred. Pipeline completes normally. |
| Language detection fails | Treat as unknown, still send to the AI, which reports `source_lang` itself. |
| Source poll fails | Existing per-source try and except plus circuit breaker behaviour is unchanged. One dead feed cannot stop a run. |
| Translation missing on a non-English item | Item is withheld from serving rather than shown in a foreign language, and retried next run. |

The pipeline must never leave the feed empty because of an AI outage. Heuristic fallback is always available.

## Testing

| Unit | Tests |
|---|---|
| `sources` | GDELT query contains theme terms, `max_records` honoured, RSS parses a fixture feed, one failing feed does not abort the run. |
| `prefilter` | Language detected on Arabic, French and English fixtures. Junk blocklist catches a sport headline and does **not** catch a debt headline. Budget cap defers the remainder. Dedup still fires. |
| `ai_grader` | Provider mocked in the existing style. Cases: relevant macro item kept, sport item rejected, passing-mention article attributed to the correct country, Arabic item translated with `source_lang` set, invalid model output falls back to `None`. |
| `persist` | Country links written with correct roles, `primary_iso3` kept in sync, trace persisted, transaction rolls back cleanly on error. |
| Endpoint | `GET /api/news?iso3=KEN` returns items linked as primary or secondary, ordered by relevance then recency. |
| Backfill | Idempotent on re-run. A known-bad seeded item is demoted and no longer served. |

Target: full suite green, including the existing 219 tests.

## Success criteria

1. No non-English text is served in any country feed.
2. A manual review of 20 items across countries finds none that are off-policy.
3. No item is filed under a country that is only mentioned in passing.
4. Every country has at least 5 items after backfill.
5. Every served item carries a rationale.
6. Feed quality survives an AI outage through heuristic fallback.

## Risks

| Risk | Mitigation |
|---|---|
| Threshold too strict, feed thins | Single env dial, plus the acceptance target that forces a check per country before shipping. |
| AI cost growth as sources widen | Pre-filters and dedup run before any AI call, per-run cap plus daily token cap bound the spend. |
| Model misjudges "material politics" | Policy stated verbatim in the prompt, rationale recorded on every item so misjudgements are visible and the prompt can be tuned. |
| Translation quality | Title and short summary only, original text and source link always retained. |
| Nightly pipeline blocking the API | `run_news_pipeline` is async and gated by `news_poll_enabled`. Any blocking call it makes must be offloaded with `asyncio.to_thread`, following the fix already applied to `run_nightly` in commit 4f6d728. |
