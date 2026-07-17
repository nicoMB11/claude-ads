import os

import pytest

from mb_rebuild import catalog as cat_mod
from mb_rebuild.utils import MbError

CATALOG_YML = """
plugins:
  - slug: elementor
    kind: plugin
    type: free
    source: wordpress.org
    latest: "3.30.0"
  - slug: elementor-pro
    kind: plugin
    type: premium
    file: elementor-pro-3.30.0.zip
    license_key_env: ELEMENTOR_PRO_LICENSE
    activation: api
    license_sites: 5
themes:
  - slug: hello-elementor
    kind: theme
    type: free
    source: wordpress.org
    latest: "3.4.2"
"""


def _make_catalog(tmp_path, text=CATALOG_YML):
    root = tmp_path / "mb-catalog"
    root.mkdir()
    (root / "catalog.yml").write_text(text)
    return str(root)


def test_load_and_lookup(tmp_path):
    cat = cat_mod.load_catalog(_make_catalog(tmp_path))
    assert cat.slugs == {"elementor", "elementor-pro", "hello-elementor"}
    assert cat.by_slug("elementor-pro").is_premium
    assert not cat.by_slug("elementor").is_premium
    assert cat.by_slug("nope") is None


def test_duplicate_slug_rejected(tmp_path):
    text = CATALOG_YML + "\n  - slug: elementor\n    kind: theme\n    type: free\n"
    with pytest.raises(MbError):
        cat_mod.load_catalog(_make_catalog(tmp_path, text))


def test_premium_requires_file(tmp_path):
    bad = """
plugins:
  - slug: acme-pro
    kind: plugin
    type: premium
    license_key_env: ACME
"""
    with pytest.raises(MbError):
        cat_mod.load_catalog(_make_catalog(tmp_path, bad))


def test_verify_flags_missing_premium_zip(tmp_path):
    cat = cat_mod.load_catalog(_make_catalog(tmp_path))
    rep = cat_mod.verify(cat)
    joined = rep.render()
    assert "Premium ZIPs MISSING" in joined
    assert "elementor-pro" in joined


def test_verify_sees_present_premium_zip(tmp_path):
    root = _make_catalog(tmp_path)
    os.makedirs(os.path.join(root, "premium"))
    open(os.path.join(root, "premium", "elementor-pro-3.30.0.zip"), "w").close()
    cat = cat_mod.load_catalog(root)
    assert "Premium ZIPs present" in cat_mod.verify(cat).render()


def test_check_licenses_hides_values(tmp_path):
    cat = cat_mod.load_catalog(_make_catalog(tmp_path))
    rep = cat_mod.check_licenses(cat, {"ELEMENTOR_PRO_LICENSE": "SECRET-KEY-123"})
    out = rep.render()
    assert "SECRET-KEY-123" not in out
    assert "Resolved" in out


def test_check_licenses_reports_unresolved(tmp_path):
    cat = cat_mod.load_catalog(_make_catalog(tmp_path))
    assert "UNRESOLVED" in cat_mod.check_licenses(cat, {}).render()


def test_license_slots_over_capacity(tmp_path):
    cat = cat_mod.load_catalog(_make_catalog(tmp_path))
    demand = {f"site{i}.com": ["elementor-pro"] for i in range(6)}  # 6 > 5
    out = cat_mod.license_slots(cat, demand).render()
    assert "OVER CAPACITY" in out
    assert "6/5" in out


def test_license_slots_within_plan(tmp_path):
    cat = cat_mod.load_catalog(_make_catalog(tmp_path))
    demand = {"a.com": ["elementor-pro"], "b.com": ["elementor-pro"]}
    out = cat_mod.license_slots(cat, demand).render()
    assert "Within plan" in out
    assert "2/5" in out


def test_download_free_dry_run_lists_urls(tmp_path):
    cat = cat_mod.load_catalog(_make_catalog(tmp_path))
    out = cat_mod.download_free(cat, dry_run=True).render()
    assert "Would download" in out
    assert "downloads.wordpress.org" in out
    # Premium items are never downloaded here.
    assert "elementor-pro" not in out
