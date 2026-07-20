"""Module 4 — assemble a clean site on the target host.

Sequence (every write is dry-run guarded):
  1. wp core download          — official WordPress (pinnable with wp_version)
  2. wp-config generated fresh — fresh salts, carried-over $table_prefix,
                                 DISALLOW_FILE_EDIT=true, WP_AUTO_UPDATE_CORE=false
  3. install plugins           — from the catalogue's official ZIPs, activate,
                                 apply licences read from .env
  4. install theme             — from the catalogue
  5. import + clean DB         — module 3
  6. uploads copied + scanned  — images rapatriated, every .php/.phtml removed
  7. hardening                 — Wordfence + 2FA + registrations closed
  8. preview override (opt.)   — WP_HOME/WP_SITEURL for preprod (remove at cutover)
  9. compliance report         — plus a per-site MANUAL-steps checklist

No file of CODE from the old site is ever copied — only DB + uploads. That
single rule is what guarantees no backdoor travels.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .catalog import Catalog, Item, item_zip_path
from .remote import Remote, rsync_pull, scp_push
from .utils import MbError, Report, info, ok, register_secret, resolve_secret, warn

# File extensions that must never exist inside uploads/.
DANGEROUS_UPLOAD_EXTS = (".php", ".phtml", ".php3", ".php4", ".php5", ".php7", ".pht", ".phar")

HARDENING_PLUGINS = ["wordfence"]


@dataclass
class SiteConfig:
    site: str
    plugins: list[str] = field(default_factory=list)
    theme: str | None = None
    php: str | None = None
    table_prefix: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "SiteConfig":
        if "site" not in data:
            raise MbError("site-config.yml missing 'site'")
        return cls(
            site=str(data["site"]),
            plugins=[str(p) for p in data.get("plugins", [])],
            theme=data.get("theme"),
            php=str(data["php"]) if data.get("php") is not None else None,
            table_prefix=data.get("table_prefix"),
        )


@dataclass
class DbConfig:
    """Credentials for the fresh wp-config on the target.

    table_prefix is carried over from the OLD site: WordPress core tables and
    every plugin's option keys are namespaced by it, so the imported DB only
    matches if wp-config uses the same prefix.
    """

    name: str
    user: str
    password: str
    host: str = "localhost"
    table_prefix: str | None = None


def manual_steps(site: str, *, preview_url: str | None = None) -> list[str]:
    """Per-site checklist of steps the CLI deliberately does NOT automate.

    Phases E/F/G of the playbook (Infomaniak Manager + Google Search Console)
    are out of CLI scope and stay manual — this list exists so they are not
    forgotten site by site.
    """
    steps = [
        "Verify the rebuilt site on the PREVIEW URL before touching DNS",
    ]
    if preview_url:
        steps.append(
            "REMOVE the preview override at cutover — "
            f"`mb-rebuild preview --target <host> --clear` (was set to {preview_url})"
        )
    steps += [
        "Infomaniak Manager: detach the domain from the old site",
        "Infomaniak Manager: attach the domain to the new site",
        "DNS: point the domain at the new host and let it propagate",
        "SSL: issue/renew the certificate for the domain on the new host",
        "Google Search Console: re-verify ownership and re-submit the sitemap",
        "Wordfence: confirm 2FA enrolment for every admin account",
    ]
    return steps


def find_dangerous_upload_files(root: str) -> list[str]:
    """Return every executable-code file under an uploads tree.

    Pure filesystem walk — unit-testable. No image is a PHP file, so any hit
    here is a backdoor to delete before the uploads reach the clean site.
    """
    hits: list[str] = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name.lower().endswith(DANGEROUS_UPLOAD_EXTS):
                hits.append(os.path.join(dirpath, name))
    return sorted(hits)


def _install_plugin(remote: Remote, cat: Catalog, item: Item, env_file: dict, rep: Report) -> None:
    zip_path = item_zip_path(cat, item)
    if item.is_premium and not (os.path.exists(zip_path) or remote.dry_run):
        raise MbError(f"premium ZIP missing for {item.slug}: {zip_path}")

    if item.is_premium:
        # Push the official ZIP and install from it.
        remote_zip = f"{remote.host.path.rstrip('/')}/mb-{item.slug}.zip"
        scp_push(remote.host, zip_path, remote_zip, dry_run=remote.dry_run)
        remote.wp(["plugin", "install", remote_zip, "--activate"], write=True)
        remote.run(["rm", "-f", remote_zip], write=True, check=False)
    else:
        version = item.latest or "latest"
        args = ["plugin", "install", item.slug, "--activate"]
        if item.latest:
            args.append(f"--version={version}")
        remote.wp(args, write=True)

    rep.add("Plugins installed (official)", f"{item.slug} ({'premium' if item.is_premium else item.latest or 'latest'})")
    _apply_license(remote, item, env_file, rep)


def _apply_license(remote: Remote, item: Item, env_file: dict, rep: Report) -> None:
    if not item.license_key_env:
        return
    key = resolve_secret(item.license_key_env, env_file)
    if not key:
        rep.add("Licence NOT applied (key unresolved)", f"{item.slug} <- ${item.license_key_env}")
        warn(f"licence for {item.slug} unresolved (${item.license_key_env}); skipping")
        return
    # Mask this exact value anywhere it appears in logs (incl. positional args).
    register_secret(key)

    if item.activation == "manual":
        rep.add(
            "Manual action — activate licence by hand",
            f"{item.slug}: Settings > License (post-it in report)",
        )
        return

    # We pass the key as an argv element; Remote shell-quotes it and redact()
    # keeps it out of logs. The catalogue never stored the value itself.
    if item.activation == "api":
        # Vendor-specific; expressed generically via the plugin's own wp subcommand.
        remote.wp([item.slug, "license", "activate", key], write=True, check=False)
    else:  # key in a field
        remote.wp(["option", "update", f"{item.slug}_license_key", key], write=True, check=False)
    rep.add("Licence applied (value hidden)", f"{item.slug} <- ${item.license_key_env}")


def build(
    remote: Remote,
    cat: Catalog,
    cfg: SiteConfig,
    env_file: dict,
    *,
    wp_version: str | None = None,
    source_uploads: str | None = None,
    staging_dir: str,
    db: DbConfig | None = None,
    preview_url: str | None = None,
    auto_update_core: bool = False,
) -> Report:
    """Run the assembly. Returns a compliance report."""
    rep = Report(title=f"Build compliance — {cfg.site}")
    remote.check_connectivity()

    # 1. Official core.
    core_args = ["core", "download", "--skip-content"]
    if wp_version:
        core_args.append(f"--version={wp_version}")
    remote.wp(core_args, write=True)
    rep.add("Core", f"official WordPress {wp_version or '(latest)'} downloaded")

    # 2. Fresh wp-config. If DB creds are given we generate it from scratch,
    #    carrying over the old site's $table_prefix (the imported DB depends on
    #    it). Otherwise we assume a wp-config already exists and only refresh
    #    salts. Either way we set the hardening constants.
    if db:
        register_secret(db.password)  # never echo the DB password in logs
        create_args = [
            "config", "create",
            f"--dbname={db.name}",
            f"--dbuser={db.user}",
            f"--dbpass={db.password}",
            f"--dbhost={db.host}",
            "--force",
        ]
        if db.table_prefix:
            create_args.append(f"--dbprefix={db.table_prefix}")
        remote.wp(create_args, write=True)
        rep.add("wp-config", f"generated fresh (table_prefix={db.table_prefix or 'wp_'})")
    else:
        rep.add("wp-config", "existing config kept (no DB creds passed); salts refreshed")

    remote.wp(["config", "shuffle-salts"], write=True, check=False)
    remote.wp(
        ["config", "set", "DISALLOW_FILE_EDIT", "true", "--raw", "--type=constant"],
        write=True,
        check=False,
    )
    # APC case: an old premium plugin was incompatible with the next major WP,
    # so core auto-updates must be pinned off and updates driven deliberately.
    remote.wp(
        ["config", "set", "WP_AUTO_UPDATE_CORE", "true" if auto_update_core else "false",
         "--raw", "--type=constant"],
        write=True,
        check=False,
    )
    rep.add(
        "wp-config hardening",
        f"fresh salts + DISALLOW_FILE_EDIT=true + WP_AUTO_UPDATE_CORE={str(auto_update_core).lower()}",
    )

    # 3. Plugins from the catalogue.
    for slug in cfg.plugins:
        item = cat.by_slug(slug)
        if not item:
            rep.add("SKIPPED plugin (not in catalogue)", f"{slug} — never installed automatically")
            warn(f"plugin '{slug}' not in catalogue; skipping (nulled guard)")
            continue
        _install_plugin(remote, cat, item, env_file, rep)

    # 4. Theme from the catalogue.
    if cfg.theme:
        titem = cat.by_slug(cfg.theme)
        if titem:
            if titem.is_premium:
                zip_path = item_zip_path(cat, titem)
                remote_zip = f"{remote.host.path.rstrip('/')}/mb-theme-{titem.slug}.zip"
                scp_push(remote.host, zip_path, remote_zip, dry_run=remote.dry_run)
                remote.wp(["theme", "install", remote_zip, "--activate"], write=True)
                remote.run(["rm", "-f", remote_zip], write=True, check=False)
            else:
                remote.wp(["theme", "install", titem.slug, "--activate"], write=True)
            rep.add("Theme", f"{cfg.theme} (official)")
        else:
            rep.add("SKIPPED theme (not in catalogue)", cfg.theme)
            warn(f"theme '{cfg.theme}' not in catalogue; skipping")

    # 5. Uploads: rapatriate + scan (delete every .php/.phtml).
    if source_uploads:
        local_uploads = os.path.join(staging_dir, "uploads")
        os.makedirs(local_uploads, exist_ok=True)
        # source_uploads is "user@host:/path"; pull with rsync.
        from .remote import Host

        src_host = Host.parse(source_uploads)
        rsync_pull(src_host, src_host.path, local_uploads, dry_run=remote.dry_run)
        if not remote.dry_run:
            removed = find_dangerous_upload_files(local_uploads)
            for path in removed:
                os.remove(path)
            rep.add("Uploads scanned", f"{len(removed)} executable file(s) removed before upload")
            # Push cleaned uploads to the target.
            target_uploads = f"{remote.host.path.rstrip('/')}/wp-content/uploads"
            _push_dir(remote, local_uploads, target_uploads)
        else:
            rep.add("Uploads (dry-run)", "would rsync from source, delete .php/.phtml, push cleaned")

    # 6. Hardening.
    for slug in HARDENING_PLUGINS:
        remote.wp(["plugin", "install", slug, "--activate"], write=True, check=False)
    remote.wp(["option", "update", "users_can_register", "0"], write=True, check=False)
    rep.add("Hardening", "Wordfence installed, registrations closed (enable 2FA in Wordfence)")

    # 7. Preview override for preprod validation. MUST be removed at cutover,
    #    which is the classic forgotten step — so it is called out below too.
    if preview_url:
        remote.wp(["config", "set", "WP_HOME", preview_url, "--type=constant"], write=True, check=False)
        remote.wp(["config", "set", "WP_SITEURL", preview_url, "--type=constant"], write=True, check=False)
        rep.add("Preview override SET", f"WP_HOME/WP_SITEURL -> {preview_url}")

    # 8. Per-site checklist of the remaining MANUAL steps (do NOT forget).
    for stepline in manual_steps(cfg.site, preview_url=preview_url):
        rep.add("Manual steps remaining (per site)", stepline)

    return rep


def set_preview(remote: Remote, url: str) -> None:
    """Pin WP_HOME/WP_SITEURL to a preview URL (preprod validation)."""
    remote.check_connectivity()
    remote.wp(["config", "set", "WP_HOME", url, "--type=constant"], write=True)
    remote.wp(["config", "set", "WP_SITEURL", url, "--type=constant"], write=True)
    if not remote.dry_run:
        ok(f"preview override set -> {url}")


def clear_preview(remote: Remote) -> None:
    """Remove the WP_HOME/WP_SITEURL override at cutover.

    The database's own siteurl/home options take over again — this is the step
    everyone forgets, so it gets its own command.
    """
    remote.check_connectivity()
    remote.wp(["config", "delete", "WP_HOME"], write=True, check=False)
    remote.wp(["config", "delete", "WP_SITEURL"], write=True, check=False)
    remote.wp(["cache", "flush"], write=True, check=False)
    if not remote.dry_run:
        ok("preview override removed (WP_HOME / WP_SITEURL)")


def _push_dir(remote: Remote, local_dir: str, remote_dir: str) -> None:
    """rsync a local dir up to the target (used for cleaned uploads)."""
    src = local_dir.rstrip("/") + "/"
    dst = f"{remote.host.target}:{remote_dir}"
    ssh = "ssh -o BatchMode=yes" + (f" -p {remote.host.port}" if remote.host.port else "")
    import subprocess

    argv = ["rsync", "-a", "-e", ssh, src, dst]
    proc = subprocess.run(argv, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise MbError(f"uploads push failed: {proc.stderr.strip()}")
    ok(f"pushed cleaned uploads -> {remote_dir}")
