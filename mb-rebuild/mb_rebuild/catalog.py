"""Module 1 — the extension catalogue.

A local, versioned, private folder holding the OFFICIAL sources of every
plugin/theme used across the fleet. `catalog.yml` lists slugs, versions and
licences; free items are fetched from wordpress.org, premium items are ZIPs
the operator placed there once, from the vendor account.

Two invariants this module enforces:
  * Licence *values* never live in the catalogue — only the NAME of the env
    var that holds them (`license_key_env`). We resolve values at run time
    from a git-ignored .env.
  * Premium code is never harvested from an existing (possibly infected)
    site. The catalogue is the single clean source of truth.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from .utils import (
    MbError,
    Report,
    info,
    ok,
    read_yaml,
    resolve_secret,
    warn,
)

WPORG_PLUGIN_URL = "https://downloads.wordpress.org/plugin/{slug}.{version}.zip"
WPORG_THEME_URL = "https://downloads.wordpress.org/theme/{slug}.{version}.zip"


@dataclass
class Item:
    """A single catalogue entry (plugin or theme)."""

    slug: str
    kind: str  # "plugin" | "theme"
    type: str = "free"  # "free" | "premium"
    source: str | None = None  # "wordpress.org" for free
    file: str | None = None  # ZIP filename for premium (under premium/ or themes/)
    latest: str | None = None  # version string for free downloads
    license_key_env: str | None = None
    activation: str = "key"  # "key" | "api" | "manual"
    license_sites: int | None = None  # slots this licence covers, if known

    @property
    def is_premium(self) -> bool:
        return self.type == "premium"


@dataclass
class Catalog:
    root: str
    plugins: list[Item] = field(default_factory=list)
    themes: list[Item] = field(default_factory=list)

    @property
    def items(self) -> list[Item]:
        return self.plugins + self.themes

    def by_slug(self, slug: str) -> Item | None:
        for item in self.items:
            if item.slug == slug:
                return item
        return None

    @property
    def slugs(self) -> set[str]:
        return {item.slug for item in self.items}


def _coerce_item(raw: dict[str, Any], kind: str) -> Item:
    if "slug" not in raw:
        raise MbError(f"catalog {kind} entry missing 'slug': {raw!r}")
    return Item(
        slug=str(raw["slug"]),
        kind=kind,
        type=str(raw.get("type", "free")),
        source=raw.get("source"),
        file=raw.get("file"),
        latest=str(raw["latest"]) if raw.get("latest") is not None else None,
        license_key_env=raw.get("license_key_env"),
        activation=str(raw.get("activation", "key")),
        license_sites=raw.get("license_sites"),
    )


def load_catalog(root: str) -> Catalog:
    """Load `<root>/catalog.yml` into a Catalog."""
    manifest = os.path.join(root, "catalog.yml")
    data = read_yaml(manifest)
    cat = Catalog(root=root)
    for raw in data.get("plugins", []) or []:
        cat.plugins.append(_coerce_item(raw, "plugin"))
    for raw in data.get("themes", []) or []:
        cat.themes.append(_coerce_item(raw, "theme"))
    _validate(cat)
    return cat


def _validate(cat: Catalog) -> None:
    seen: set[str] = set()
    for item in cat.items:
        if item.slug in seen:
            raise MbError(f"duplicate slug in catalog: {item.slug}")
        seen.add(item.slug)
        if item.is_premium:
            if not item.file:
                raise MbError(
                    f"premium item '{item.slug}' must declare a 'file' (its ZIP)"
                )
            # A premium item that activates by key/api needs a licence env name.
            if item.activation in {"key", "api"} and not item.license_key_env:
                warn(
                    f"premium item '{item.slug}' activates by {item.activation} "
                    "but has no license_key_env — activation will be skipped"
                )
        else:
            if item.source not in {"wordpress.org", None}:
                warn(f"free item '{item.slug}' has unusual source '{item.source}'")


def item_zip_path(cat: Catalog, item: Item) -> str:
    """Absolute path to the ZIP that would install this item."""
    if item.is_premium:
        subdir = "themes" if item.kind == "theme" else "premium"
        return os.path.join(cat.root, subdir, item.file or "")
    # Free items live in free/ (plugins) or themes/ after download.
    subdir = "themes" if item.kind == "theme" else "free"
    version = item.latest or "latest"
    return os.path.join(cat.root, subdir, f"{item.slug}-{version}.zip")


def verify(cat: Catalog) -> Report:
    """Check that every catalogue item resolves to a present, official source.

    * premium ZIPs must exist on disk
    * free items must be downloadable (we don't fetch here, just report)
    * licence env vars must be resolvable (value not shown)
    """
    report = Report(title="Catalog verification")
    for item in cat.items:
        zip_path = item_zip_path(cat, item)
        if item.is_premium:
            if os.path.exists(zip_path):
                report.add("Premium ZIPs present", f"{item.slug} -> {os.path.basename(zip_path)}")
            else:
                report.add("Premium ZIPs MISSING", f"{item.slug} -> {zip_path}")
        else:
            state = "cached" if os.path.exists(zip_path) else "will download from wordpress.org"
            report.add("Free items", f"{item.slug} ({item.latest or 'latest'}) — {state}")
    return report


def check_licenses(cat: Catalog, env_file: dict[str, str]) -> Report:
    """Report licence resolvability WITHOUT printing any key value."""
    report = Report(title="Licence key resolution")
    for item in cat.items:
        if not item.license_key_env:
            continue
        value = resolve_secret(item.license_key_env, env_file)
        if value:
            report.add("Resolved (value hidden)", f"{item.slug} <- ${item.license_key_env}")
        else:
            report.add(
                "UNRESOLVED",
                f"{item.slug} <- ${item.license_key_env} (set it in .env or the environment)",
            )
    return report


def license_slots(cat: Catalog, demanding_slugs_per_site: dict[str, list[str]]) -> Report:
    """Compare licence coverage vs demand — Point de vigilance n°4.

    demanding_slugs_per_site maps site -> list of catalogue slugs that site
    needs. For every premium item with a declared license_sites count, we
    report covered slots vs the number of sites requesting it, and warn when
    demand exceeds the plan.
    """
    report = Report(title="Licence slots (coverage vs demand)")
    for item in cat.items:
        if not item.is_premium:
            continue
        demanders = [
            site for site, slugs in demanding_slugs_per_site.items() if item.slug in slugs
        ]
        covered = item.license_sites
        if covered is None:
            report.add(
                "Unknown coverage",
                f"{item.slug}: {len(demanders)} site(s) demand it, license_sites not set",
            )
            continue
        line = f"{item.slug}: {len(demanders)}/{covered} slots used"
        if len(demanders) > covered:
            report.add(
                "OVER CAPACITY",
                f"{line} — {', '.join(demanders)} (deactivate on an old site first!)",
            )
        else:
            report.add("Within plan", line)
    return report


def download_free(cat: Catalog, *, dry_run: bool, only: list[str] | None = None) -> Report:
    """Download official ZIPs for free items from wordpress.org.

    Uses requests when available. In dry-run, only reports the URLs. Never
    touches premium items (those come from the vendor account, placed once).
    """
    report = Report(title="Free downloads")
    targets = [
        i for i in cat.items if not i.is_premium and (only is None or i.slug in only)
    ]
    if not targets:
        report.add("Nothing to do", "no free items match")
        return report

    for item in targets:
        version = item.latest or "latest"
        tmpl = WPORG_THEME_URL if item.kind == "theme" else WPORG_PLUGIN_URL
        url = tmpl.format(slug=item.slug, version=version)
        dest = item_zip_path(cat, item)
        if os.path.exists(dest):
            report.add("Skipped (cached)", f"{item.slug} {version}")
            continue
        if dry_run:
            report.add("Would download", f"{item.slug} {version} <- {url}")
            continue
        _http_download(url, dest)
        report.add("Downloaded", f"{item.slug} {version}")
        ok(f"downloaded {item.slug} {version}")
    return report


def _http_download(url: str, dest: str) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        import requests
    except ImportError as exc:  # pragma: no cover - env dependent
        raise MbError("requests is required to download; pip install requests") from exc

    info(f"GET {url}")
    with requests.get(url, stream=True, timeout=60) as resp:
        if resp.status_code != 200:
            raise MbError(f"download failed ({resp.status_code}) for {url}")
        tmp = dest + ".part"
        with open(tmp, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                fh.write(chunk)
        os.replace(tmp, dest)
