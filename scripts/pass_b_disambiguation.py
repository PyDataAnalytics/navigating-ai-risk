"""Pass B: add `disambiguation` field to each entry.

For every name in adjacent_to.similar, the entry must have a disambiguation
line keyed by that name. The line tells the matcher: "pick THIS entry when X,
pick the SIBLING when Y."

IDEMPOTENT. Behavior:
- If disambiguation field is missing, create it with empty placeholders.
- If a similar-sibling lacks a disambiguation entry, add it with the placeholder.
- If a sibling is removed from `similar` (e.g., Pass A re-classifies it as `related`),
  remove the stale disambiguation key.
- Existing authored text is preserved.

Authored disambiguations live in `scripts/disambiguation_content.py`. The split
keeps content separate from mechanism, so authoring sessions don't touch the
script and re-running the script doesn't risk overwriting content.

Usage:
    python scripts/pass_b_disambiguation.py
    # then validate
    pytest tests/test_adjacencies.py
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "config"
DEFS_PATH = CONFIG / "subcategory_definitions.yaml"
TAXONOMY_PATH = CONFIG / "taxonomy.yaml"

PLACEHOLDER = "TODO: write disambiguation"


def _swap_halves(text: str) -> str | None:
    """Convert 'A-half; B-half.' into 'B-half; A-half.' for use as the reverse-
    direction disambiguation.

    Returns None if the text doesn't follow the expected two-half template.

    Convention: by authoring convention, both halves are written to be readable
    starting with an entry name (capitalized). The swap simply exchanges the
    halves and re-punctuates — no case change is needed because both halves
    were written to start mid-sentence-readable.

    Examples:
        'A for X; B for Y.' → 'B for Y; A for X.'
    """
    if text == PLACEHOLDER:
        return None
    parts = text.split("; ")
    if len(parts) != 2:
        return None
    left, right = parts
    # The right half ends in a period; strip it, then re-add at the end after swap.
    right_clean = right.rstrip(".")
    # Swap: new sentence is "{right_clean}; {left}."
    return f"{right_clean}; {left}."


def main() -> int:
    defs = yaml.safe_load(DEFS_PATH.read_text())
    taxonomy = yaml.safe_load(TAXONOMY_PATH.read_text())

    # Load authored content (separate module to keep this script stable)
    try:
        from scripts.disambiguation_content import DISAMBIGUATIONS  # type: ignore
    except ImportError:
        import sys

        sys.path.insert(0, str(REPO))
        try:
            from scripts.disambiguation_content import DISAMBIGUATIONS  # type: ignore
        except ImportError:
            DISAMBIGUATIONS = {}

    added = 0
    removed = 0
    placeholders = 0
    derived_count = 0
    from_module = 0

    # Authored content (the module) is the sole source of truth for explicit
    # disambiguations. The file is a derived artifact and gets overwritten.
    # If a (source, sibling) pair has no module entry but its reverse does,
    # the reverse is auto-derived via swap-halves.

    for sc in defs["subcategories"]:
        name = sc["name"]
        similar_set = set(sc["adjacent_to"]["similar"])

        existing = sc.get("disambiguation", {}) or {}
        if not isinstance(existing, dict):
            existing = {}

        new_disambig: dict[str, str] = {}
        for sibling in sc["adjacent_to"]["similar"]:
            # 1) Authored content module wins
            authored = DISAMBIGUATIONS.get((name, sibling))
            if authored:
                new_disambig[sibling] = authored
                from_module += 1
                if sibling not in existing:
                    added += 1
                continue

            # 2) Auto-derive from the forward-direction module entry if it exists
            forward = DISAMBIGUATIONS.get((sibling, name))
            if forward:
                derived_text = _swap_halves(forward)
                if derived_text:
                    new_disambig[sibling] = derived_text
                    derived_count += 1
                    if sibling not in existing:
                        added += 1
                    continue

            # 3) Placeholder for unauthored edges
            new_disambig[sibling] = PLACEHOLDER
            placeholders += 1
            if sibling not in existing:
                added += 1

        # Detect stale keys (was in similar before, now removed from similar)
        for stale_key in existing:
            if stale_key not in similar_set:
                removed += 1

        sc["disambiguation"] = new_disambig

    # Emit file (preserving ordering and category banners)
    cat_boundaries = []
    idx = 0
    for cat in taxonomy["categories"]:
        start = idx
        idx += len(cat["subcategories"])
        cat_boundaries.append((start, idx, cat["name"]))

    _write_yaml(defs, cat_boundaries)

    print(f"disambiguation entries added:     {added}")
    print(f"disambiguation entries from module: {from_module}")
    print(f"disambiguation entries derived:   {derived_count}")
    print(f"disambiguation entries removed:   {removed}")
    print(f"placeholders remaining:           {placeholders}")
    return 0


def _emit_entry(entry: dict, indent: str = "  ") -> str:
    lines = [
        f'{indent}- name: "{entry["name"]}"',
        f"{indent}  nature: {entry['nature']}",
        f"{indent}  confidence: {entry['confidence']}",
        f'{indent}  one_line: "{entry["one_line"].replace(chr(34), chr(92) + chr(34))}"',
    ]
    for field in ("applies_when", "does_not_apply_when", "user_signals"):
        lines.append(f"{indent}  {field}:")
        for item in entry[field]:
            esc = item.replace('"', '\\"')
            lines.append(f'{indent}    - "{esc}"')
    lines.append(f"{indent}  adjacent_to:")
    for rel_key in ("similar", "related"):
        items = entry["adjacent_to"].get(rel_key, [])
        if items:
            lines.append(f"{indent}    {rel_key}:")
            for item in items:
                esc = item.replace('"', '\\"')
                lines.append(f'{indent}      - "{esc}"')
        else:
            lines.append(f"{indent}    {rel_key}: []")
    # Disambiguation field
    disambig = entry.get("disambiguation", {})
    if disambig:
        lines.append(f"{indent}  disambiguation:")
        for sibling in entry["adjacent_to"]["similar"]:
            if sibling in disambig:
                key_esc = sibling.replace('"', '\\"')
                val_esc = disambig[sibling].replace('"', '\\"')
                lines.append(f'{indent}    "{key_esc}": "{val_esc}"')
    else:
        lines.append(f"{indent}  disambiguation: {{}}")
    lines.append(f"{indent}  elements:")
    for elem in (
        "threat",
        "event",
        "operational_artifacts",
        "mitigations_controls",
        "regulatory_standards",
        "research",
    ):
        e = entry["elements"][elem]
        lines.append(f"{indent}    {elem}:")
        lines.append(f"{indent}      population: {e['population']}")
        if "notes" in e:
            notes = e["notes"].replace('"', '\\"')
            lines.append(f'{indent}      notes: "{notes}"')
    return "\n".join(lines)


def _write_yaml(defs: dict, cat_boundaries: list[tuple[int, int, str]]) -> None:
    header = (
        "# AI Risk Taxonomy — Subcategory Definitions (v2.2)\n"
        "# =====================================================\n"
        "# Expert-revised v2 with: nature, confidence, applies_when, does_not_apply_when,\n"
        "# user_signals, adjacent_to (typed: similar / related), disambiguation\n"
        "# (per-sibling tie-break text), and elements (6 populations).\n"
        "#\n"
        "# adjacent_to.similar:  close concepts the matcher might consider switching to\n"
        "# adjacent_to.related:  connected but distinct concepts the matcher might mention\n"
        '# disambiguation:       per-sibling line: "pick THIS when X, pick SIBLING when Y"\n'
        "#                       keys must equal adjacent_to.similar exactly\n"
        "#\n"
        "# Names match taxonomy.yaml exactly — this is the interface contract.\n"
        "#\n"
        "# Version: 2.2\n"
        "\n"
        'version: "2.2"\n'
    )
    out = [header, "subcategories:", ""]
    for start, end, title in cat_boundaries:
        out.append("  # " + "═" * 68)
        out.append(f"  # {title}")
        out.append("  # " + "═" * 68)
        out.append("")
        for i in range(start, end):
            out.append(_emit_entry(defs["subcategories"][i]))
            out.append("")
    DEFS_PATH.write_text("\n".join(out))


if __name__ == "__main__":
    raise SystemExit(main())
