import os

from mb_rebuild import catalog as cat_mod
from mb_rebuild.build import SiteConfig, find_dangerous_upload_files
from mb_rebuild.detect import Detection, _slug_from_plugin_file, report


def test_slug_from_plugin_file():
    assert _slug_from_plugin_file("elementor/elementor.php") == "elementor"
    assert _slug_from_plugin_file("hello.php") == "hello"
    assert _slug_from_plugin_file("woocommerce/woocommerce.php") == "woocommerce"


def test_detection_to_site_config_keeps_only_known():
    det = Detection(
        site="example.com",
        known_plugins=["elementor", "woocommerce"],
        unknown_plugins=["all-in-one-wp-migration"],
        theme="hello-elementor",
        theme_known=True,
        php="8.2",
    )
    cfg = det.to_site_config()
    assert cfg["plugins"] == ["elementor", "woocommerce"]
    assert "all-in-one-wp-migration" not in cfg["plugins"]
    assert cfg["theme"] == "hello-elementor"
    assert cfg["php"] == "8.2"


def test_detection_unknown_theme_not_written():
    det = Detection(site="x.com", theme="nulled-theme", theme_known=False)
    assert "theme" not in det.to_site_config()


def test_report_flags_unknown_plugin_as_nulled():
    det = Detection(site="x.com", unknown_plugins=["all-in-one-wp-migration"])
    out = report(det).render()
    assert "UNKNOWN plugins" in out
    assert "all-in-one-wp-migration" in out


def test_find_dangerous_upload_files(tmp_path):
    up = tmp_path / "uploads" / "2024" / "05"
    up.mkdir(parents=True)
    (up / "photo.jpg").write_bytes(b"\xff\xd8\xff")
    (up / "shell.php").write_text("<?php system($_GET['c']); ?>")
    (up / "evil.phtml").write_text("<?php ?>")
    (up / "logo.PNG").write_bytes(b"\x89PNG")
    hits = find_dangerous_upload_files(str(tmp_path / "uploads"))
    names = {os.path.basename(h) for h in hits}
    assert names == {"shell.php", "evil.phtml"}


def test_site_config_from_dict_requires_site():
    import pytest

    from mb_rebuild.utils import MbError

    with pytest.raises(MbError):
        SiteConfig.from_dict({"plugins": ["x"]})


def test_site_config_roundtrip():
    cfg = SiteConfig.from_dict(
        {"site": "s.com", "plugins": ["elementor"], "theme": "hello-elementor", "php": "8.2"}
    )
    assert cfg.site == "s.com"
    assert cfg.plugins == ["elementor"]
    assert cfg.theme == "hello-elementor"


def test_detection_carries_table_prefix():
    det = Detection(site="x.com", table_prefix="wp_abc_")
    assert det.to_site_config()["table_prefix"] == "wp_abc_"


def test_site_config_reads_table_prefix():
    cfg = SiteConfig.from_dict({"site": "s.com", "table_prefix": "wp_xyz_"})
    assert cfg.table_prefix == "wp_xyz_"


def test_manual_steps_include_infomaniak_and_gsc():
    from mb_rebuild.build import manual_steps

    steps = manual_steps("poeles.com")
    joined = "\n".join(steps)
    assert "Infomaniak" in joined
    assert "DNS" in joined
    assert "Search Console" in joined
    assert "2FA" in joined


def test_manual_steps_flag_preview_removal_when_set():
    from mb_rebuild.build import manual_steps

    steps = manual_steps("poeles.com", preview_url="https://preprod.example.com")
    assert any("REMOVE the preview override" in s for s in steps)
