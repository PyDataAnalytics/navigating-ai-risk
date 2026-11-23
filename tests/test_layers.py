"""Guard for the taxonomy's structural division into layers.

The taxonomy has two layers that answer different questions and draw on
different literatures:

    adversarial  a hostile actor is required
    operational  no actor required; a control is absent or unexecuted

The v1.0 categories are deliberately left as they stand and rely on the
`layer` default, so this file pins that default rather than requiring every
existing block to be edited.
"""

from pathlib import Path

import pytest
import yaml

from ai_risk_retrieval.models import Taxonomy

CONFIG = Path(__file__).resolve().parent.parent / "config"
VALID_BANDS = {"service_operations", "risk_and_compliance", "governance_and_oversight"}

# The v1.0 categories. None of these may silently become operational.
V1_CATEGORY_IDS = {
    "technical_reliability",
    "safety",
    "security_cyber",
    "privacy",
    "ethical",
    "social_cultural",
    "economic_labor",
    "political_geopolitical",
    "legal_compliance",
    "organizational_business",
    "environmental",
    "cognitive_psychological",
    "scientific_knowledge",
    "existential",
    "meta_risks",
}


@pytest.fixture(scope="module")
def taxonomy() -> Taxonomy:
    return Taxonomy.model_validate(yaml.safe_load((CONFIG / "taxonomy.yaml").read_text("utf-8")))


def test_v1_categories_all_present_and_adversarial(taxonomy):
    """The existing part is kept as is: all 15 present, all still adversarial.

    The completeness half matters: without it, a typo in V1_CATEGORY_IDS makes
    this test pass by matching nothing.
    """
    present = {c.id for c in taxonomy.categories}
    missing = V1_CATEGORY_IDS - present
    assert not missing, f"v1.0 categories missing from the taxonomy: {sorted(missing)}"
    wrong = [
        c.id for c in taxonomy.categories if c.id in V1_CATEGORY_IDS and c.layer != "adversarial"
    ]
    assert not wrong, f"v1.0 categories moved out of the adversarial layer: {wrong}"


def test_operational_categories_declare_a_band(taxonomy):
    missing = [c.id for c in taxonomy.layer("operational") if not c.band]
    assert not missing, f"operational categories without a band: {missing}"


def test_bands_are_known(taxonomy):
    bad = [(c.id, c.band) for c in taxonomy.layer("operational") if c.band not in VALID_BANDS]
    assert not bad, f"unknown bands (expected {VALID_BANDS}): {bad}"


def test_adversarial_categories_have_no_band(taxonomy):
    """`band` groups the operational layer only; the model enforces this too."""
    bad = [c.id for c in taxonomy.layer("adversarial") if c.band is not None]
    assert not bad, f"adversarial categories carrying a band: {bad}"


def test_every_category_is_in_exactly_one_layer(taxonomy):
    total = len(taxonomy.layer("adversarial")) + len(taxonomy.layer("operational"))
    assert total == len(taxonomy.categories)


def test_operational_category_ids_are_prefixed(taxonomy):
    """`ops_` prefix keeps the division legible in ids, logs and output paths."""
    bad = [c.id for c in taxonomy.layer("operational") if not c.id.startswith("ops_")]
    assert not bad, f"operational category ids without the ops_ prefix: {bad}"
