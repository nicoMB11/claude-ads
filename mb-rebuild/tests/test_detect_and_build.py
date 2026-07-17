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
