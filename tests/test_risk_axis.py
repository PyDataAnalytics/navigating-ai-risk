"""Guard for config/risk_axis.yaml — the operational/adversarial structural axis.

Mirrors the taxonomy drift guard in test_adjacencies.py: the axis file must stay
one-to-one with the taxonomy, so a subcategory can never be added without a
decision recorded about whether it needs an adversary.
"""

from pathlib import Path

import pytest
import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config"
VALID_ADVERSARY = {"none", "inbound", "outbound"}


@pytest.fixture(scope="module")
def axis():
    return yaml.safe_load((CONFIG / "risk_axis.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def canonical_names():
    tax = yaml.safe_load((CONFIG / "taxonomy.yaml").read_text(encoding="utf-8"))
    return [s["name"] for c in tax["categories"] for s in c["subcategories"]]


def test_axis_covers_every_subcategory(axis, canonical_names):
    named = {e["name"] for e in axis["subcategories"]}
    missing = [n for n in canonical_names if n not in named]
    assert not missing, f"Subcategories with no adversary axis recorded: {missing}"


def test_axis_has_no_unknown_names(axis, canonical_names):
    canonical = set(canonical_names)
    extra = [e["name"] for e in axis["subcategories"] if e["name"] not in canonical]
    assert not extra, f"Axis entries not present in the taxonomy: {extra}"


def test_axis_values_valid(axis):
    bad = [
        (e["name"], e.get("adversary"))
        for e in axis["subcategories"]
        if e.get("adversary") not in VALID_ADVERSARY
    ]
    assert not bad, f"Invalid adversary values (expected {VALID_ADVERSARY}): {bad}"


def test_axis_has_no_duplicates(axis):
    names = [e["name"] for e in axis["subcategories"]]
    dups = {n for n in names if names.count(n) > 1}
    assert not dups, f"Duplicate axis entries: {dups}"


def test_known_adversarial_entries_are_not_typed_none(axis):
    """Regression: these were all `nature: operational`, indistinguishable from
    control failures such as 'Failed AI deployments'."""
    by_name = {e["name"]: e["adversary"] for e in axis["subcategories"]}
    for name in [
        "Prompt injection attacks",
        "Jailbreaks",
        "Data poisoning",
        "Model theft",
        "Compromised training pipelines",
    ]:
        if name in by_name:
            assert by_name[name] == "inbound", f"{name} should be adversary: inbound"
    for name in [
        "Automated phishing by AI",
        "Malware generation by LLMs",
        "Deepfake impersonation",
    ]:
        if name in by_name:
            assert by_name[name] == "outbound", f"{name} should be adversary: outbound"


def test_control_failures_need_no_adversary(axis):
    by_name = {e["name"]: e["adversary"] for e in axis["subcategories"]}
    for name in [
        "Poor monitoring or observability",
        "Failed AI deployments",
        "Vendor lock-in for AI",
    ]:
        if name in by_name:
            assert by_name[name] == "none", f"{name} should be adversary: none"
