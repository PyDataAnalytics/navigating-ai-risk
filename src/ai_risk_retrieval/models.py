"""
Data models. All cross-component data passes through these.

Pydantic is used here not just for ergonomics but as a *security boundary*:
LLM output and source API responses are parsed against these models; anything
that doesn't conform is rejected before it can corrupt downstream state.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from .net import UnsafeUrlError, safe_http_url

# ─── Taxonomy ────────────────────────────────────────────────────────────────


class Subcategory(BaseModel):
    """A leaf node in the risk taxonomy."""

    name: str = Field(min_length=2, max_length=200)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    # Negative anchors: things the judge should explicitly *not* count as
    # matching this subcategory. Especially useful for ambiguous names where
    # the model might match on the wrong sense (e.g. "Hallucinations" → medical
    # hallucinations rather than LLM hallucinations). Threaded into the judge
    # system prompt; bounded length to keep the prompt budget predictable.
    excludes: list[str] = Field(default_factory=list, max_length=10)
    target_papers: int | None = Field(default=None, ge=1, le=10)

    @property
    def slug(self) -> str:
        """File-system-safe identifier."""
        return (
            self.name.lower()
            .replace(" ", "-")
            .replace("/", "-")
            .replace("&", "and")
            .replace("'", "")
        )


class Category(BaseModel):
    """A top-level risk category.

    `layer` is the structural division of the taxonomy. The two layers answer
    different questions and draw on different literatures, so they are kept
    apart rather than interleaved:

      adversarial  a hostile actor is required. Remove the attacker and the
                   risk disappears. Attack-and-defence literature.
      operational  no actor required. The risk is realised by a control being
                   absent, mis-specified or unexecuted. Governance, assurance
                   and service-management literature.

    It defaults to "adversarial" so the v1.0 categories validate unchanged -
    the existing taxonomy is deliberately left as it stands.

    `band` groups the operational layer by where the work actually sits
    (service operations / risk and compliance / governance and oversight). It
    is None for the adversarial layer.

    A paper may legitimately be selected in BOTH layers: the corpus is
    paper-centric with one `placements` entry per slot, so a paper covering an
    attack and its control is stored once with a placement in each.
    """

    id: str = Field(pattern=r"^[a-z0-9_]+$", max_length=64)
    name: str = Field(min_length=2, max_length=200)
    layer: Literal["adversarial", "operational"] = "adversarial"
    band: str | None = Field(default=None, max_length=64)
    subcategories: list[Subcategory] = Field(min_length=1)

    @model_validator(mode="after")
    def _band_only_on_operational(self) -> Category:
        if self.band is not None and self.layer != "operational":
            raise ValueError(
                f"category {self.id!r}: `band` is only meaningful on the operational layer"
            )
        return self


class Taxonomy(BaseModel):
    version: str
    default_target_papers: int = Field(default=3, ge=1, le=10)
    categories: list[Category] = Field(min_length=1)

    def all_subcategories(self) -> list[tuple[Category, Subcategory]]:
        return [(c, s) for c in self.categories for s in c.subcategories]

    def layer(self, name: str) -> list[Category]:
        """Categories in one structural layer: "adversarial" or "operational"."""
        return [c for c in self.categories if c.layer == name]

    def bands(self) -> dict[str, list[Category]]:
        """Operational-layer categories grouped by band, in declaration order."""
        out: dict[str, list[Category]] = {}
        for c in self.categories:
            if c.layer == "operational":
                out.setdefault(c.band or "ungrouped", []).append(c)
        return out

    def find_subcategory(self, name: str) -> tuple[Category, Subcategory] | None:
        for c in self.categories:
            for s in c.subcategories:
                if s.name.lower() == name.lower():
                    return c, s
        return None


# ─── Papers ──────────────────────────────────────────────────────────────────

SourceName = Literal[
    "arxiv", "semantic_scholar", "papers_with_code", "ssrn", "google_scholar", "openalex"
]


class Paper(BaseModel):
    """
    A candidate paper. Treated as untrusted input until evaluated.

    Constraints here defend against malformed or hostile source data:
    - Lengths are bounded so a single paper can't blow up a prompt.
    - URLs are validated: `url`/`pdf_url` as HttpUrl, and `oa_pdf_url` through
      net.safe_http_url, which also refuses private, loopback and link-local
      hosts and embedded credentials. Both block javascript:/file:/data:.
    - content_hash is computed by the fetcher; immutable through the pipeline.
    """

    title: str = Field(min_length=1, max_length=500)
    abstract: str = Field(default="", max_length=10_000)
    authors: list[str] = Field(default_factory=list, max_length=200)
    year: int | None = Field(default=None, ge=1900, le=2100)
    # Full publication date when the source provides one (arXiv, OpenAlex,
    # Semantic Scholar all do). Day-granularity is the unit that matters for
    # downstream temporal analysis (emerging-theme / freshness work); `year`
    # is retained as a coarse fallback for sources that only expose a year.
    publication_date: date | None = Field(default=None)
    venue: str | None = Field(default=None, max_length=300)
    citation_count: int | None = Field(default=None, ge=0)

    # Identifiers — at least one should be present for dedup
    doi: str | None = Field(default=None, max_length=200)
    arxiv_id: str | None = Field(default=None, max_length=50)
    semantic_scholar_id: str | None = Field(default=None, max_length=100)

    url: HttpUrl
    pdf_url: HttpUrl | None = None
    # Legal open-access PDF located by Unpaywall (optional; populated only when
    # UNPAYWALL_EMAIL is set — see enrichment/unpaywall.py). Kept as a plain
    # string rather than HttpUrl because it is assigned post-construction by the
    # enrichment step, but it is NOT unchecked: `model_config` below turns on
    # assignment validation and `_validate_oa_pdf_url` vets the value.
    #
    # The previous comment here reasoned that the field "is only ever set to a
    # real Unpaywall URL". That conflated provenance with trust: the value is
    # `best_oa_location.url_for_pdf`, which the PUBLISHER supplies, not
    # Unpaywall. Without assignment validation this field accepted any string —
    # `http://169.254.169.254/...` and a 50,000-character value both went
    # through, and excerpt_agent.py prefers this field over the HttpUrl-checked
    # `pdf_url` when choosing what to fetch.
    oa_pdf_url: str | None = Field(default=None, max_length=2000)

    source: SourceName
    fetched_at: datetime
    content_hash: str = Field(min_length=64, max_length=64)  # sha256 hex

    # Assignment validation matters here specifically because `oa_pdf_url` is
    # populated after construction; without it the field's own constraints and
    # validator never run.
    model_config = ConfigDict(validate_assignment=True)

    @field_validator("oa_pdf_url")
    @classmethod
    def _validate_oa_pdf_url(cls, v: str | None) -> str | None:
        """Vet the publisher-supplied open-access URL before anything fetches it."""
        if v is None:
            return None
        try:
            return safe_http_url(v, field="oa_pdf_url")
        except UnsafeUrlError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("publication_date", mode="before")
    @classmethod
    def _parse_publication_date(cls, v: object) -> date | None:
        """Normalize whatever a source hands us into a real date (day granularity).

        Accepts, in order: an existing date/datetime, an int year, a full ISO
        datetime string (arXiv: '2024-01-15T17:00:00Z'), a 'YYYY-MM-DD' string
        (OpenAlex / Semantic Scholar publicationDate), a 'YYYY-MM' string, or a
        bare 'YYYY'. Anything unparseable becomes None rather than raising, so a
        malformed date never drops an otherwise-good paper.
        """
        if v is None or v == "":
            return None
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, date):
            return v
        if isinstance(v, int):
            try:
                return date(v, 1, 1)
            except ValueError:
                return None
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            # Full ISO datetime or 'YYYY-MM-DD' (datetime.fromisoformat accepts both)
            try:
                return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
            except ValueError:
                pass
            # 'YYYY-MM-DD' as a pure date, if the above missed it
            try:
                return date.fromisoformat(s[:10])
            except ValueError:
                pass
            # 'YYYY-MM' or 'YYYY' → first of the period
            if len(s) >= 4 and s[:4].isdigit():
                try:
                    return date(int(s[:4]), 1, 1)
                except ValueError:
                    return None
        return None

    @field_validator("arxiv_id")
    @classmethod
    def _validate_arxiv_id(cls, v: str | None) -> str | None:
        if v is None:
            return v
        # arXiv IDs look like 2310.12345 or hep-th/9901001. Strict allow-list.
        import re

        if not re.fullmatch(r"[a-z\-]+(\.[A-Z]{2})?/\d{7}|\d{4}\.\d{4,5}(v\d+)?", v):
            raise ValueError(f"invalid arxiv_id: {v!r}")
        return v

    @field_validator("doi")
    @classmethod
    def _validate_doi(cls, v: str | None) -> str | None:
        if v is None:
            return v
        import re

        if not re.fullmatch(r"10\.\d{4,9}/[\w.\-;()/:]+", v):
            raise ValueError(f"invalid DOI: {v!r}")
        return v

    def dedup_key(self) -> str:
        """Stable key for cross-source dedup."""
        if self.doi:
            return f"doi:{self.doi.lower()}"
        if self.arxiv_id:
            # Strip version suffix
            base = self.arxiv_id.split("v")[0] if "v" in self.arxiv_id else self.arxiv_id
            return f"arxiv:{base}"
        # Fall back to normalized title; fuzzy dedup handles the rest
        return f"title:{self.title.lower().strip()}"


# ─── Scoring ─────────────────────────────────────────────────────────────────


class LLMJudgement(BaseModel):
    """
    Strict schema for LLM output. The judge MUST return JSON matching this.

    Bounded ranges and short string limits prevent the LLM from exfiltrating
    arbitrary data through the score field or stuffing the rationale with
    follow-on prompt injection attempts that downstream components might
    re-render unsafely.
    """

    relevance: float = Field(ge=0.0, le=10.0)
    rationale: str = Field(max_length=500)

    @field_validator("rationale")
    @classmethod
    def _clean_rationale(cls, v: str) -> str:
        # Strip control chars and any HTML-like content. The rationale is shown
        # in a webapp; we don't want an injected <script> or markdown link there.
        import re

        v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", v)
        v = re.sub(r"<[^>]+>", "", v)  # naive HTML strip
        return v.strip()


class ScoredPaper(BaseModel):
    """A paper plus its judgement plus the composite final score."""

    paper: Paper
    llm: LLMJudgement
    composite_score: float = Field(ge=0.0, le=10.0)
    # For audit/debugging
    score_components: dict[str, float] = Field(default_factory=dict)


# ─── Output ──────────────────────────────────────────────────────────────────


class SubcategoryResult(BaseModel):
    category_id: str
    category_name: str
    subcategory_name: str
    selected_papers: list[ScoredPaper]
    candidate_count: int
    shortlist_count: int
    generated_at: datetime


class RetrievalRun(BaseModel):
    """Top-level output document."""

    schema_version: str = "1.0"
    run_id: str
    started_at: datetime
    finished_at: datetime
    taxonomy_version: str
    llm_model: str
    results: list[SubcategoryResult]
