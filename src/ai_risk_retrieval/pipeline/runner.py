"""
Top-level runner. Composes sources, dedup, shortlist, judge, rank.

Concurrency: subcategories run in parallel up to `runtime.concurrency`.
Within one subcategory, source fetches run concurrently (5 sources at once
is fine — they're independent hosts and the budget is bounded).
LLM scoring is sequential per subcategory because Ollama is typically a
single-GPU bottleneck; parallel calls just queue up.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import structlog

from ..config import AppConfig
from ..evaluator import BinaryScreener, LLMJudge
from ..evaluator.query_expander import QueryExpander
from ..models import (
    Category,
    Paper,
    RetrievalRun,
    Subcategory,
    SubcategoryResult,
    Taxonomy,
)
from ..sources import (
    ArxivSource,
    GoogleScholarSource,
    OpenAlexSource,
    PaperSource,
    PapersWithCodeSource,
    SemanticScholarSource,
    SSRNSource,
)
from .dedup import deduplicate
from .diversify import mmr_select
from .rank import compute_composite_scores, shortlist_for_judging

log = structlog.get_logger()


def _build_sources(config: AppConfig) -> list[PaperSource]:
    timeout = config.runtime.per_request_timeout_seconds
    return [
        ArxivSource(config.sources.arxiv, timeout),
        SemanticScholarSource(config.sources.semantic_scholar, timeout),
        OpenAlexSource(config.sources.openalex, timeout),
        PapersWithCodeSource(config.sources.papers_with_code, timeout),
        SSRNSource(config.sources.ssrn, timeout),
        GoogleScholarSource(config.sources.google_scholar, timeout),
    ]


async def run_subcategory(
    category: Category,
    subcategory,
    sources: list[PaperSource],
    judge: LLMJudge,
    config: AppConfig,
    expander: QueryExpander | None = None,
    screener: BinaryScreener | None = None,
) -> SubcategoryResult:
    """Run the full pipeline for a single subcategory."""
    log.info("subcategory_start", category=category.name, subcategory=subcategory.name)

    # 0. Query expansion: get LLM-generated synonyms/related terms, then build
    # an augmented Subcategory whose `keywords` field carries the expansions.
    # Sources read `subcategory.name + subcategory.keywords` for their query,
    # so this lifts recall across every source with no per-source changes.
    # The expander is cached on disk: each subcategory is expanded once per
    # (taxonomy version, model). The original `subcategory` is preserved for
    # downstream LLM judging and the results output.
    fetch_subcategory = subcategory
    if expander is not None:
        try:
            expanded_keywords = await expander.expand(subcategory)
            # `expand()` returns name + originals + LLM expansions, all merged
            # and de-duplicated. Strip the name out — Subcategory.keywords
            # shouldn't duplicate the name, and sources OR-join name+keywords
            # already.
            keywords_only = [q for q in expanded_keywords if q.lower() != subcategory.name.lower()]
            fetch_subcategory = Subcategory(
                name=subcategory.name,
                keywords=keywords_only[:20],  # Subcategory caps at 20
                excludes=subcategory.excludes,  # preserve negative anchors
                target_papers=subcategory.target_papers,
            )
            log.info(
                "queries_expanded",
                subcategory=subcategory.name,
                original_keywords=len(subcategory.keywords),
                effective_keywords=len(fetch_subcategory.keywords),
            )
        except Exception as e:
            # Expansion is best-effort. Never let it fail the whole run.
            log.warning("expansion_failed_using_base", subcategory=subcategory.name, error=str(e))

    # 1. Fetch from all sources concurrently
    fetch_tasks = [s.fetch(fetch_subcategory) for s in sources]
    fetched_lists = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    candidates: list[Paper] = []
    for source, result in zip(sources, fetched_lists, strict=True):
        if isinstance(result, Exception):
            log.warning(
                "source_failed",
                source=source.name,
                subcategory=subcategory.name,
                error=str(result),
            )
            continue
        candidates.extend(result)

    log.info("fetched", subcategory=subcategory.name, count=len(candidates))

    # 2. Filter by age and abstract length
    candidates = _filter_candidates(candidates, config)

    # 3. Dedup
    candidates = deduplicate(candidates, fuzzy_threshold=config.retrieval.title_dedup_threshold)
    log.info("after_dedup", subcategory=subcategory.name, count=len(candidates))

    # 4. Shortlist. When the binary screener is enabled we build an *extended*
    # shortlist (e.g. 50 papers) and feed it through the cheap screener; the
    # survivors are then trimmed to llm_shortlist_size for the expensive
    # detailed judge. When the screener is disabled, we use llm_shortlist_size
    # directly and the behavior matches single-stage judging.
    screen_enabled = screener is not None and config.llm_screen.enabled
    if screen_enabled:
        pre_screen = shortlist_for_judging(candidates, config.retrieval.screen_shortlist_size)
    else:
        pre_screen = shortlist_for_judging(candidates, config.retrieval.llm_shortlist_size)

    # 4b. Binary relevance screen (cheap model, yes/no). Survivors-only flow
    # forward. None return values (timeout, parse failure) are treated as
    # "let it through" to avoid silently dropping candidates on transient
    # errors — matches the graceful-fallback principle used by the expander.
    if screen_enabled:
        screened: list[Paper] = []
        for paper in pre_screen:
            verdict = await screener.screen(paper, subcategory)
            if verdict is False:
                continue
            screened.append(paper)
        log.info(
            "screened",
            subcategory=subcategory.name,
            pre_screen=len(pre_screen),
            survivors=len(screened),
        )
        # Trim survivors to the detailed-judge budget. Survivors retain the
        # cheap-heuristic order, so this keeps the most plausible ones.
        shortlist = screened[: config.retrieval.llm_shortlist_size]
    else:
        shortlist = pre_screen

    # 5. LLM judging (sequential — Ollama bottleneck)
    judged: list[tuple[Paper, LLMJudgement]] = []  # noqa: F821
    for paper in shortlist:
        judgement = await judge.score(paper, subcategory)
        if judgement is None:
            continue
        judged.append((paper, judgement))

    # 6. Composite ranking
    scored = compute_composite_scores(judged, config.scoring)

    # 7. Apply minimum-score threshold first (drop weak papers regardless of
    # diversity), then use MMR to pick the final target_papers from survivors.
    # MMR favors papers that are both high-scoring *and* dissimilar to ones
    # already selected — avoiding three near-duplicate follow-up papers from
    # the same research group sweeping all slots. λ=1 collapses to pure
    # composite-score order (set via scoring.diversity_lambda).
    target = subcategory.target_papers or 3
    above_threshold = [
        sp for sp in scored if sp.composite_score >= config.scoring.min_acceptable_score
    ]
    selected = mmr_select(
        above_threshold,
        target=target,
        lam=config.scoring.diversity_lambda,
    )

    log.info(
        "subcategory_done",
        category=category.name,
        subcategory=subcategory.name,
        candidates=len(candidates),
        shortlisted=len(shortlist),
        judged=len(judged),
        selected=len(selected),
    )

    return SubcategoryResult(
        category_id=category.id,
        category_name=category.name,
        subcategory_name=subcategory.name,
        selected_papers=selected,
        candidate_count=len(candidates),
        shortlist_count=len(shortlist),
        generated_at=datetime.now(timezone.utc),
    )


def _filter_candidates(papers: list[Paper], config: AppConfig) -> list[Paper]:
    """Apply basic quality filters before dedup."""
    out = []
    current_year = datetime.now(timezone.utc).year
    max_age = config.retrieval.max_age_years
    min_abs = config.retrieval.min_abstract_chars

    for p in papers:
        if max_age is not None and p.year is not None:
            if (current_year - p.year) > max_age:
                continue
        if len(p.abstract or "") < min_abs:
            continue
        out.append(p)
    return out


async def run_full(
    taxonomy: Taxonomy,
    config: AppConfig,
    subcategory_filter: str | None = None,
) -> RetrievalRun:
    """Run the full pipeline over the entire taxonomy (or a single subcategory)."""
    sources = _build_sources(config)
    judge = LLMJudge(config.llm, audit_log_path=config.runtime.audit_log_path)
    # Binary screener (stage-1 cheap relevance filter). Only constructed when
    # enabled in config — otherwise stays None and the runner skips the screen.
    screener: BinaryScreener | None = None
    if config.llm_screen.enabled:
        # The screener config is a separate LLMScreenConfig type, but the
        # BinaryScreener constructor expects an LLMConfig-shaped object.
        # We pass the screen config directly — the fields it reads (host,
        # model, temperature, num_ctx, request_timeout_seconds, max_input_chars)
        # are identical across both types.
        screener = BinaryScreener(
            config=config.llm_screen,  # type: ignore[arg-type]
            audit_log_path=config.runtime.audit_log_path,
        )
        log.info("screener_enabled", model=config.llm_screen.model)
    # Query expander: cached on disk under runtime.cache_directory. Re-runs
    # against the same taxonomy version hit the cache and make zero LLM calls
    # for expansion.
    expansion_cache_path = f"{config.runtime.cache_directory.rstrip('/')}/query_expansion.json"
    expander = QueryExpander(
        config=config.llm,
        cache_path=expansion_cache_path,
        taxonomy_version=taxonomy.version,
    )

    pairs = taxonomy.all_subcategories()
    if subcategory_filter:
        pairs = [(c, s) for c, s in pairs if s.name.lower() == subcategory_filter.lower()]
        if not pairs:
            raise ValueError(f"no subcategory found matching {subcategory_filter!r}")

    started = datetime.now(timezone.utc)
    sem = asyncio.Semaphore(config.runtime.concurrency)

    async def _run_one(c: Category, s) -> SubcategoryResult:
        async with sem:
            return await run_subcategory(c, s, sources, judge, config, expander, screener)

    results = await asyncio.gather(*[_run_one(c, s) for c, s in pairs])

    # Optional Unpaywall OA-link enrichment of the SELECTED papers only.
    # Fully gated on UNPAYWALL_EMAIL and best-effort: when the env var is unset
    # this is a no-op, and any failure is logged without aborting the run.
    try:
        from ..enrichment.unpaywall import enrich_papers, unpaywall_email

        if unpaywall_email():
            selected_papers = [sp.paper for r in results for sp in r.selected_papers]
            added = await enrich_papers(selected_papers)
            log.info(
                "unpaywall_enriched",
                papers=len(selected_papers),
                oa_links_added=added,
            )
    except Exception as e:
        log.warning("unpaywall_enrichment_skipped", error=str(e))

    finished = datetime.now(timezone.utc)

    return RetrievalRun(
        run_id=str(uuid.uuid4()),
        started_at=started,
        finished_at=finished,
        taxonomy_version=taxonomy.version,
        llm_model=config.llm.model,
        results=list(results),
    )
