"""Command-line interface for mb-rebuild.

Subcommands, in the order the brief prescribes (read-only first, build last):

    catalog verify|licenses|slots|download   inspect/fill the catalogue
    detect                                    generate site-config.yml (read-only)
    db-scan                                   export + scan a source DB (report only)
    db-import                                 import cleaned DB into target
    build                                     full assembly

Safety: every writing command defaults to --dry-run. Pass --apply to execute.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .utils import MbError, error, info, load_env_file, ok, set_quiet, warn


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--catalog", default="mb-catalog", help="path to the catalogue root (default: mb-catalog)")
    p.add_argument("--env-file", default=".env", help="path to the git-ignored .env (default: .env)")
    p.add_argument("--quiet", action="store_true", help="suppress info output")


def _add_write_flags(p: argparse.ArgumentParser) -> None:
    # Dry-run is the default; --apply turns it off. We store the effective
    # dry_run in a single place so subcommands never diverge.
    p.add_argument(
        "--apply",
        dest="dry_run",
        action="store_false",
        default=True,
        help="actually execute writes (default is --dry-run)",
    )


def _remote(args, spec_attr: str):
    from .remote import Host, Remote

    spec = getattr(args, spec_attr)
    host = Host.parse(spec, port=getattr(args, "port", None))
    return Remote(host, dry_run=getattr(args, "dry_run", True))


# --------------------------------------------------------------------------
# Command handlers
# --------------------------------------------------------------------------


def cmd_catalog(args) -> int:
    from . import catalog as cat_mod

    cat = cat_mod.load_catalog(args.catalog)
    env_file = load_env_file(args.env_file)

    if args.catalog_cmd == "verify":
        print(cat_mod.verify(cat).render())
    elif args.catalog_cmd == "licenses":
        print(cat_mod.check_licenses(cat, env_file).render())
    elif args.catalog_cmd == "download":
        only = args.only.split(",") if args.only else None
        print(cat_mod.download_free(cat, dry_run=args.dry_run, only=only).render())
    elif args.catalog_cmd == "slots":
        demand = _load_demand(args.site_configs)
        print(cat_mod.license_slots(cat, demand).render())
    else:  # pragma: no cover
        raise MbError(f"unknown catalog subcommand: {args.catalog_cmd}")
    return 0


def _load_demand(paths: list[str]) -> dict[str, list[str]]:
    from .build import SiteConfig
    from .utils import read_yaml

    demand: dict[str, list[str]] = {}
    for path in paths:
        cfg = SiteConfig.from_dict(read_yaml(path))
        demand[cfg.site] = list(cfg.plugins) + ([cfg.theme] if cfg.theme else [])
    return demand


def cmd_detect(args) -> int:
    from . import catalog as cat_mod
    from . import detect as det_mod

    cat = cat_mod.load_catalog(args.catalog)
    remote = _remote(args, "source")
    det = det_mod.detect_source(remote, cat, site=args.site or remote.host.host)
    print(det_mod.report(det).render())
    if args.out:
        det_mod.write_site_config(det, args.out)
        ok(f"site-config written to {args.out}")
    else:
        info("pass --out site-config.yml to persist the generated config")
    return 0


def cmd_db_scan(args) -> int:
    from . import dbclean

    remote = _remote(args, "source")
    os.makedirs(args.workdir, exist_ok=True)
    dump = os.path.join(args.workdir, "source-db.sql")
    dbclean.export_source(remote, dump)
    if remote.dry_run or not os.path.exists(dump):
        warn("dry-run: no dump to scan (use --apply to export and scan for real)")
        return 0
    with open(dump, encoding="utf-8", errors="replace") as fh:
        sql = fh.read()
    findings = dbclean.scan_dump(sql, admin_whitelist=_split(args.admin_whitelist))
    rep = dbclean.report(findings, dump_path=dump)
    print(rep.render())
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write(rep.render())
        ok(f"scan report written to {args.report}")
    return 0


def cmd_db_import(args) -> int:
    from . import dbclean

    source = _remote(args, "source")
    target = _remote(args, "target")
    os.makedirs(args.workdir, exist_ok=True)
    dump = os.path.join(args.workdir, "source-db.sql")

    dbclean.export_source(source, dump)
    if not source.dry_run and os.path.exists(dump):
        with open(dump, encoding="utf-8", errors="replace") as fh:
            findings = dbclean.scan_dump(fh.read(), admin_whitelist=_split(args.admin_whitelist))
    else:
        findings = dbclean.Findings()
    print(dbclean.report(findings, dump_path=dump).render())

    if not args.yes and not target.dry_run:
        warn("refusing to import without --yes (validate the scan report first)")
        return 2

    dbclean.import_and_clean(
        target,
        dump,
        findings,
        admin_whitelist=_split(args.admin_whitelist),
        remove_users=args.remove_users,
    )
    return 0


def cmd_build(args) -> int:
    from . import catalog as cat_mod
    from .build import SiteConfig, build
    from .utils import read_yaml

    cat = cat_mod.load_catalog(args.catalog)
    cfg = SiteConfig.from_dict(read_yaml(args.site))
    env_file = load_env_file(args.env_file)
    remote = _remote(args, "target")
    os.makedirs(args.workdir, exist_ok=True)

    rep = build(
        remote,
        cat,
        cfg,
        env_file,
        wp_version=args.wp_version,
        source_uploads=args.source_uploads,
        staging_dir=args.workdir,
    )
    print(rep.render())
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write(rep.render())
        ok(f"compliance report written to {args.report}")
    return 0


def _split(value: str | None) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()] if value else []


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mb-rebuild",
        description="Rebuild clean WordPress sites from official sources.",
    )
    parser.add_argument("--version", action="version", version=f"mb-rebuild {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # catalog. Common args live on each leaf so they can follow the leaf name.
    c = sub.add_parser("catalog", help="inspect and fill the extension catalogue")
    csub = c.add_subparsers(dest="catalog_cmd", required=True)
    cv = csub.add_parser("verify", help="check every item resolves to an official source")
    _add_common(cv)
    cl = csub.add_parser("licenses", help="report licence-key resolvability (values hidden)")
    _add_common(cl)
    cd = csub.add_parser("download", help="download free items from wordpress.org")
    _add_common(cd)
    cd.add_argument("--only", help="comma-separated slugs to download")
    _add_write_flags(cd)
    cs = csub.add_parser("slots", help="compare licence coverage vs demand")
    _add_common(cs)
    cs.add_argument("site_configs", nargs="+", help="one or more site-config.yml files")
    c.set_defaults(func=cmd_catalog)

    # detect
    d = sub.add_parser("detect", help="read a source site and generate site-config.yml")
    _add_common(d)
    d.add_argument("--source", required=True, help="user@host:/path of the OLD site")
    d.add_argument("--port", type=int, help="SSH port")
    d.add_argument("--site", help="site name for the config (default: source host)")
    d.add_argument("--out", help="write the generated site-config.yml here")
    d.set_defaults(func=cmd_detect, dry_run=True)

    # db-scan
    s = sub.add_parser("db-scan", help="export + scan a source DB (report only)")
    _add_common(s)
    s.add_argument("--source", required=True, help="user@host:/path of the OLD site")
    s.add_argument("--port", type=int, help="SSH port")
    s.add_argument("--workdir", default="mb-work", help="local snapshot directory")
    s.add_argument("--admin-whitelist", help="comma-separated allowed admin logins")
    s.add_argument("--report", help="write the scan report to this file")
    _add_write_flags(s)
    s.set_defaults(func=cmd_db_scan)

    # db-import
    di = sub.add_parser("db-import", help="import a cleaned DB into the target")
    _add_common(di)
    di.add_argument("--source", required=True, help="user@host:/path of the OLD site")
    di.add_argument("--target", required=True, help="user@host:/path of the NEW site")
    di.add_argument("--port", type=int, help="SSH port (both hosts)")
    di.add_argument("--workdir", default="mb-work", help="local snapshot directory")
    di.add_argument("--admin-whitelist", help="comma-separated allowed admin logins")
    di.add_argument("--remove-users", action="store_true", help="delete rogue admins (destructive)")
    di.add_argument("--yes", action="store_true", help="confirm import after reviewing the scan")
    _add_write_flags(di)
    di.set_defaults(func=cmd_db_import)

    # build
    b = sub.add_parser("build", help="assemble a clean site on the target")
    _add_common(b)
    b.add_argument("--site", required=True, help="path to site-config.yml")
    b.add_argument("--target", required=True, help="user@host:/path of the NEW site")
    b.add_argument("--port", type=int, help="SSH port")
    b.add_argument("--wp-version", help="pin a WordPress core version")
    b.add_argument("--source-uploads", help="user@host:/path/wp-content/uploads to rapatriate")
    b.add_argument("--workdir", default="mb-work", help="local staging directory")
    b.add_argument("--report", help="write the compliance report here")
    _add_write_flags(b)
    b.set_defaults(func=cmd_build)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    set_quiet(getattr(args, "quiet", False))
    try:
        return args.func(args)
    except MbError as exc:
        error(str(exc))
        return 1
    except KeyboardInterrupt:  # pragma: no cover
        error("interrupted")
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
