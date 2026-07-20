"""Module 2 — detect the old site's stack and generate site-config.yml.

Read-only. Reads wp_options on the source host (active plugins + active
theme) over SSH/WP-CLI, then keeps ONLY the extensions that exist in the
official catalogue. Anything the old site runs but the catalogue does not
know about is flagged (possible nulled / injected plugin) and NEVER added
to the generated config — the rebuild filters infection by construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .catalog import Catalog
from .remote import Remote
from .utils import MbError, Report, info, warn, write_yaml


@dataclass
class Detection:
    site: str
    known_plugins: list[str] = field(default_factory=list)
    unknown_plugins: list[str] = field(default_factory=list)
    theme: str | None = None
    theme_known: bool = False
    php: str | None = None
    table_prefix: str | None = None

    def to_site_config(self) -> dict:
        cfg: dict = {"site": self.site, "plugins": self.known_plugins}
        if self.theme and self.theme_known:
            cfg["theme"] = self.theme
        if self.php:
            cfg["php"] = self.php
        if self.table_prefix:
            cfg["table_prefix"] = self.table_prefix
        return cfg


def _slug_from_plugin_file(plugin_file: str) -> str:
    """`elementor/elementor.php` -> `elementor`; `hello.php` -> `hello`."""
    return plugin_file.split("/", 1)[0].removesuffix(".php")


def detect_source(remote: Remote, catalog: Catalog, *, site: str) -> Detection:
    """Inspect the source host and classify its plugins/theme vs the catalogue."""
    remote.check_connectivity()

    active = remote.wp_json(["option", "get", "active_plugins", "--format=json"]) or []
    if not isinstance(active, list):
        raise MbError("unexpected active_plugins format from source")

    det = Detection(site=site)
    for plugin_file in active:
        slug = _slug_from_plugin_file(str(plugin_file))
        if catalog.by_slug(slug):
            det.known_plugins.append(slug)
        else:
            det.unknown_plugins.append(slug)

    # Active theme: stylesheet is the child (or the theme), template the parent.
    stylesheet = remote.wp(["option", "get", "stylesheet"]).stdout.strip()
    det.theme = stylesheet or None
    det.theme_known = bool(stylesheet and catalog.by_slug(stylesheet))
    if stylesheet and not det.theme_known:
        warn(f"active theme '{stylesheet}' is not in the catalogue — add it before build")

    # PHP version is best-effort; the source may not expose it.
    php_proc = remote.run(
        ["php", "-r", "echo PHP_MAJOR_VERSION.'.'.PHP_MINOR_VERSION;"], check=False
    )
    if php_proc and php_proc.returncode == 0:
        det.php = (php_proc.stdout or "").strip() or None

    # $table_prefix must be carried over — the imported DB depends on it.
    prefix_proc = remote.wp(["config", "get", "table_prefix"], check=False)
    if prefix_proc and prefix_proc.returncode == 0:
        det.table_prefix = (prefix_proc.stdout or "").strip() or None

    return det


def report(det: Detection) -> Report:
    rep = Report(title=f"Detection — {det.site}")
    for slug in det.known_plugins:
        rep.add("Catalogued plugins (will be reinstalled from official ZIPs)", slug)
    for slug in det.unknown_plugins:
        rep.add(
            "UNKNOWN plugins (nulled? — flagged, NOT installed)",
            f"{slug} — verify against a vendor source before adding to the catalogue",
        )
    if det.theme:
        label = "Catalogued theme" if det.theme_known else "UNKNOWN theme (add to catalogue)"
        rep.add(label, det.theme)
    if det.php:
        rep.add("Detected PHP", det.php)
    if det.table_prefix:
        rep.add("Detected table_prefix (carried over to wp-config)", det.table_prefix)
    return rep


def write_site_config(det: Detection, path: str) -> None:
    write_yaml(path, det.to_site_config())
    info(f"wrote {path}")
