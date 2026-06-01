"""Tests for adjacency structure and taxonomy alignment.

Covers Pass A (typed adjacent_to) and Pass D (taxonomy drift guard).
Run via: pytest tests/test_adjacencies.py
"""

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "config"


@pytest.fixture(scope="module")
def taxonomy():
    return yaml.safe_load((CONFIG / "taxonomy.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def definitions():
    return yaml.safe_load((CONFIG / "subcategory_definitions.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def signatures():
    return yaml.safe_load((CONFIG / "subcategory_signatures.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def canonical_names(taxonomy):
    """Set of all canonical subcategory names from taxonomy.yaml."""
    return {sub["name"] for cat in taxonomy["categories"] for sub in cat["subcategories"]}


@pytest.fixture(scope="module")
def canonical_order(taxonomy):
    """Canonical subcategory names in taxonomy order."""
    return [sub["name"] for cat in taxonomy["categories"] for sub in cat["subcategories"]]


# ============================================================================
# Pass D: Taxonomy drift guard
# ============================================================================


def test_definitions_match_taxonomy_count(definitions, canonical_names):
    """Definitions must have exactly the canonical count of entries."""
    assert len(definitions["subcategories"]) == len(canonical_names), (
        f"Expected {len(canonical_names)} entries, got {len(definitions['subcategories'])}"
    )


def test_signatures_match_taxonomy_count(signatures, canonical_names):
    """Signatures must have exactly the canonical count of entries."""
    assert len(signatures["signatures"]) == len(canonical_names), (
        f"Expected {len(canonical_names)} entries, got {len(signatures['signatures'])}"
    )


def test_definitions_names_all_canonical(definitions, canonical_names):
    """Every definition name must be in taxonomy.yaml verbatim."""
    bad = [sc["name"] for sc in definitions["subcategories"] if sc["name"] not in canonical_names]
    assert not bad, f"Non-canonical names in definitions: {bad}"


def test_signatures_names_all_canonical(signatures, canonical_names):
    """Every signature name must be in taxonomy.yaml verbatim."""
    bad = [sg["name"] for sg in signatures["signatures"] if sg["name"] not in canonical_names]
    assert not bad, f"Non-canonical names in signatures: {bad}"


def test_definitions_in_canonical_order(definitions, canonical_order):
    """Definitions must be in canonical taxonomy order."""
    def_names = [sc["name"] for sc in definitions["subcategories"]]
    assert def_names == canonical_order, "Definitions not in canonical order"


def test_signatures_in_canonical_order(signatures, canonical_order):
    """Signatures must be in canonical taxonomy order."""
    sig_names = [sg["name"] for sg in signatures["signatures"]]
    assert sig_names == canonical_order, "Signatures not in canonical order"


def test_definitions_no_duplicates(definitions):
    """No duplicate subcategory names in definitions."""
    names = [sc["name"] for sc in definitions["subcategories"]]
    dups = [n for n in set(names) if names.count(n) > 1]
    assert not dups, f"Duplicate names: {dups}"


def test_signatures_no_duplicates(signatures):
    """No duplicate subcategory names in signatures."""
    names = [sg["name"] for sg in signatures["signatures"]]
    dups = [n for n in set(names) if names.count(n) > 1]
    assert not dups, f"Duplicate names: {dups}"


# ============================================================================
# Pass A: Typed adjacent_to structure and integrity
# ============================================================================


def test_adjacent_to_has_typed_shape(definitions):
    """adjacent_to must be a dict with 'similar' and 'related' keys."""
    bad = []
    for sc in definitions["subcategories"]:
        adj = sc.get("adjacent_to")
        if not isinstance(adj, dict):
            bad.append((sc["name"], "not a dict"))
            continue
        if "similar" not in adj:
            bad.append((sc["name"], "missing 'similar'"))
        if "related" not in adj:
            bad.append((sc["name"], "missing 'related'"))
    assert not bad, f"Shape violations: {bad}"


def test_adjacent_to_lists_are_lists(definitions):
    """Both similar and related must be lists (possibly empty)."""
    bad = []
    for sc in definitions["subcategories"]:
        adj = sc["adjacent_to"]
        if not isinstance(adj["similar"], list):
            bad.append((sc["name"], "similar not list"))
        if not isinstance(adj["related"], list):
            bad.append((sc["name"], "related not list"))
    assert not bad, f"Type violations: {bad}"


def test_adjacent_to_references_canonical(definitions, canonical_names):
    """Every adjacency target must be a canonical subcategory name."""
    bad = []
    for sc in definitions["subcategories"]:
        adj = sc["adjacent_to"]
        for bucket in ("similar", "related"):
            for tgt in adj[bucket]:
                if tgt not in canonical_names:
                    bad.append((sc["name"], bucket, tgt))
    assert not bad, f"Broken references: {bad}"


def test_no_self_loops(definitions):
    """No entry lists itself as an adjacency."""
    bad = []
    for sc in definitions["subcategories"]:
        adj = sc["adjacent_to"]
        for bucket in ("similar", "related"):
            if sc["name"] in adj[bucket]:
                bad.append((sc["name"], bucket))
    assert not bad, f"Self-loops: {bad}"


def test_no_duplicates_within_bucket(definitions):
    """Within similar (and within related), no duplicates."""
    bad = []
    for sc in definitions["subcategories"]:
        adj = sc["adjacent_to"]
        for bucket in ("similar", "related"):
            items = adj[bucket]
            if len(items) != len(set(items)):
                dups = [x for x in set(items) if items.count(x) > 1]
                bad.append((sc["name"], bucket, dups))
    assert not bad, f"Duplicates within bucket: {bad}"


def test_no_duplicates_across_buckets(definitions):
    """A name in similar must not also appear in related (and vice versa)."""
    bad = []
    for sc in definitions["subcategories"]:
        adj = sc["adjacent_to"]
        overlap = set(adj["similar"]) & set(adj["related"])
        if overlap:
            bad.append((sc["name"], list(overlap)))
    assert not bad, f"Cross-bucket duplicates: {bad}"


def test_at_least_one_neighbor_per_entry(definitions):
    """Every entry should have at least one neighbor in either bucket.

    Isolated entries indicate authoring oversight, not a structural impossibility.
    """
    bad = []
    for sc in definitions["subcategories"]:
        adj = sc["adjacent_to"]
        if not adj["similar"] and not adj["related"]:
            bad.append(sc["name"])
    assert not bad, f"Isolated entries (no neighbors): {bad}"


# ============================================================================
# Required field presence (defense in depth — separate from schema validation)
# ============================================================================

REQUIRED_TOP_FIELDS = [
    "name",
    "nature",
    "confidence",
    "one_line",
    "applies_when",
    "does_not_apply_when",
    "user_signals",
    "adjacent_to",
    "disambiguation",
    "elements",
]
REQUIRED_ELEMENTS = [
    "threat",
    "event",
    "operational_artifacts",
    "mitigations_controls",
    "regulatory_standards",
    "research",
]
VALID_NATURE = {"operational", "regulatory", "behavioral", "systemic"}
VALID_CONFIDENCE = {"low", "medium", "high"}
VALID_POPULATION = {"empty", "light", "moderate", "heavy"}
PLACEHOLDER = "TODO: write disambiguation"


def test_required_fields_present(definitions):
    bad = []
    for sc in definitions["subcategories"]:
        missing = [f for f in REQUIRED_TOP_FIELDS if f not in sc]
        if missing:
            bad.append((sc["name"], missing))
    assert not bad, f"Missing fields: {bad}"


def test_required_elements_present(definitions):
    bad = []
    for sc in definitions["subcategories"]:
        elems = sc.get("elements", {})
        missing = [e for e in REQUIRED_ELEMENTS if e not in elems]
        if missing:
            bad.append((sc["name"], missing))
    assert not bad, f"Missing elements: {bad}"


def test_nature_values_valid(definitions):
    bad = [
        (sc["name"], sc["nature"])
        for sc in definitions["subcategories"]
        if sc["nature"] not in VALID_NATURE
    ]
    assert not bad, f"Invalid nature: {bad}"


def test_confidence_values_valid(definitions):
    bad = [
        (sc["name"], sc["confidence"])
        for sc in definitions["subcategories"]
        if sc["confidence"] not in VALID_CONFIDENCE
    ]
    assert not bad, f"Invalid confidence: {bad}"


def test_population_values_valid(definitions):
    bad = []
    for sc in definitions["subcategories"]:
        for elem_name, elem in sc["elements"].items():
            pop = elem.get("population")
            if pop not in VALID_POPULATION:
                bad.append((sc["name"], elem_name, pop))
    assert not bad, f"Invalid populations: {bad}"


# ============================================================================
# Pass B: disambiguation field invariants
# ============================================================================


def test_disambiguation_is_dict(definitions):
    """Every entry's disambiguation field must be a dict (possibly empty)."""
    bad = []
    for sc in definitions["subcategories"]:
        d = sc.get("disambiguation")
        if not isinstance(d, dict):
            bad.append((sc["name"], type(d).__name__))
    assert not bad, f"Non-dict disambiguation fields: {bad}"


def test_disambiguation_keys_match_similar(definitions):
    """disambiguation keys must equal adjacent_to.similar exactly.

    No keys for non-similar siblings (would be stale).
    No similar siblings without keys (would leave matcher without tie-break text).
    """
    bad = []
    for sc in definitions["subcategories"]:
        similar = set(sc["adjacent_to"]["similar"])
        disambig = set(sc.get("disambiguation", {}).keys())
        missing = similar - disambig
        extra = disambig - similar
        if missing or extra:
            bad.append((sc["name"], {"missing": sorted(missing), "extra": sorted(extra)}))
    assert not bad, f"disambiguation/similar mismatch: {bad}"


def test_disambiguation_values_nonempty(definitions):
    """No empty disambiguation values. Placeholders are allowed during authoring
    but tracked separately so the count is visible."""
    bad = []
    for sc in definitions["subcategories"]:
        for sibling, text in sc.get("disambiguation", {}).items():
            if not isinstance(text, str) or not text.strip():
                bad.append((sc["name"], sibling))
    assert not bad, f"Empty disambiguation values: {bad}"
