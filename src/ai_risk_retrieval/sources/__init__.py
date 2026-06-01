"""Source adapters: fetch candidate papers from various academic search engines."""

from .arxiv import ArxivSource
from .base import PaperSource
from .google_scholar import GoogleScholarSource
from .openalex import OpenAlexSource
from .papers_with_code import PapersWithCodeSource
from .semantic_scholar import SemanticScholarSource
from .ssrn import SSRNSource

__all__ = [
    "PaperSource",
    "ArxivSource",
    "SemanticScholarSource",
    "PapersWithCodeSource",
    "SSRNSource",
    "GoogleScholarSource",
    "OpenAlexSource",
]
