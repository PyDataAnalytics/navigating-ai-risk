"""Optional, env-gated enrichment steps that run over selected papers.

These are best-effort: each is gated on an environment variable and never
aborts a run on failure. When the relevant env var is unset, the step is a
complete no-op and the pipeline behaves exactly as if the module were absent.
"""
