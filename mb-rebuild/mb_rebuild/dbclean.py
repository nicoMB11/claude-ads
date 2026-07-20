"""Module 3 — the database: export, scan, clean, import.

The database is the black hole of every WordPress clean-up. Files get all
the attention while the re-infector is often an autoloaded wp_options row
that runs on every page load. This module treats the DB with the same rigour
as the filesystem.

Detections hardened against a real infection (APC playbook):
  * the `sc_` scope-connector option family (self-recovering, self-spreading)
    without false-matching the legitimate `wpsc_` plugin;
  * a malicious cron event `sc_cron_fetch` on a custom `sc_interval`;
  * base64 payloads are DECODED before scanning — a JS cloaking injector was
    hidden base64-encoded inside an autoloaded option whose NAME was an MD5
    hash, so every literal grep missed it;
  * any autoloaded option whose name is a 32-hex MD5 hash is flagged;
  * fake admins are deleted WITH their usermeta and their posts REASSIGNED
    to a legitimate account (never orphaned).

Flow: export -> scan -> report for validation -> import + auto-remediate the
safe categories. Content-level spam in wp_posts is reported, never rewritten
(that would damage the design we are preserving).
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field

from .remote import Remote, scp_pull, scp_push
from .utils import MbError, Report, dry, info, ok, warn

# --------------------------------------------------------------------------
# Infection markers. These run over the raw SQL dump text.
# --------------------------------------------------------------------------

_CODE_MARKERS = [
    re.compile(r"<\?php", re.I),
    re.compile(r"\beval\s*\(", re.I),
    re.compile(r"base64_decode\s*\(", re.I),
    re.compile(r"gzinflate\s*\(", re.I),
    re.compile(r"str_rot13\s*\(", re.I),
    re.compile(r"create_function\s*\(", re.I),
    re.compile(r"assert\s*\(", re.I),
    re.compile(r"\bpreg_replace\s*\(\s*['\"].*/e", re.I),
]

_SCRIPT_MARKERS = [
    re.compile(r"<script[^>]*>", re.I),
    re.compile(r"document\.write\s*\(", re.I),
    re.compile(r"eval\s*\(atob\s*\(", re.I),
]

# Signatures that only reveal themselves AFTER base64 decoding — the cloaking
# injector seen on APC (redirect/counter network, JS data-URI, DOM scrubbing).
_CLOAKING_MARKERS = [
    re.compile(r"yadro", re.I),
    re.compile(r"counter\.yadro\.ru", re.I),
    re.compile(r"data:text/javascript", re.I),
    re.compile(r"bodyNode\.remove", re.I),
]

# Outbound spam themes commonly injected into posts.
_SPAM_WORDS = [
    "casino", "viagra", "cialis", "poker", "betting", "sportsbet",
    "payday loan", "porn", "escort", "replica watch",
]
_SPAM_RE = re.compile("|".join(re.escape(w) for w in _SPAM_WORDS), re.I)

# Rows we specifically care about in wp_options autoload.
_AUTOLOAD_ROW_RE = re.compile(
    r"\(\s*\d+\s*,\s*'([^']+)'\s*,\s*'(.*?)'\s*,\s*'(?:yes|on|auto)'\s*\)",
    re.S,
)

# Scope-connector family. Anchored to the FULL option name so `wpsc_feed_list`
# (a legitimate plugin, starts with `wpsc_`) can never match — only names that
# start with `sc_` (optionally wrapped in a transient prefix) are caught.
_SC_NAME_RE = re.compile(
    r"^(?:_transient_|_site_transient_|_transient_timeout_|_site_transient_timeout_)?sc_[a-z0-9_]+$",
    re.I,
)

# An autoloaded option whose NAME is a bare 32-hex MD5 hash is never legitimate.
_MD5_NAME_RE = re.compile(r"^[a-f0-9]{32}$", re.I)

# Long base64-looking runs inside an option value.
_B64_RE = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")

# The malicious cron hook and its custom schedule name.
_SC_CRON_HOOK = "sc_cron_fetch"
_SC_CRON_INTERVAL = "sc_interval"


@dataclass
class Findings:
    autoloaded_code: list[str] = field(default_factory=list)
    scope_connector_options: list[str] = field(default_factory=list)
    hash_named_options: list[str] = field(default_factory=list)
    cloaking_options: list[str] = field(default_factory=list)
    malicious_cron: list[str] = field(default_factory=list)
    injected_scripts: int = 0
    spam_posts: int = 0
    application_passwords: bool = False
    admin_users: list[str] = field(default_factory=list)
    rogue_admins: list[str] = field(default_factory=list)
    cron_present: bool = False

    @property
    def options_to_delete(self) -> list[str]:
        """Every autoloaded option name that remediation should remove."""
        names = (
            self.autoloaded_code
            + self.scope_connector_options
            + self.hash_named_options
            + self.cloaking_options
        )
        return list(dict.fromkeys(names))

    def any(self) -> bool:
        return bool(
            self.options_to_delete
            or self.malicious_cron
            or self.injected_scripts
            or self.spam_posts
            or self.application_passwords
            or self.rogue_admins
            or self.cron_present
        )


def _decode_b64_blobs(value: str) -> str:
    """Return the concatenated base64-decoded blobs found in `value`.

    An attacker hides a JS/PHP payload base64-encoded so literal greps miss
    it. We decode every long base64 run and hand the plaintext back to the
    scanners. Non-decodable runs are skipped.
    """
    decoded: list[str] = []
    for blob in _B64_RE.findall(value):
        # base64 length must be a multiple of 4; trim to be lenient.
        trimmed = blob[: len(blob) - (len(blob) % 4)]
        if len(trimmed) < 40:
            continue
        try:
            raw = base64.b64decode(trimmed, validate=False)
        except Exception:  # noqa: BLE001 - any decode failure is just a skip
            continue
        text = raw.decode("utf-8", errors="ignore")
        if text.isprintable() or any(c.isalpha() for c in text):
            decoded.append(text)
    return "\n".join(decoded)


def scan_dump(sql_text: str, admin_whitelist: list[str] | None = None) -> Findings:
    """Statically scan a SQL dump for infection markers.

    Pure function — no I/O — so it is unit-testable. Base64 payloads are
    decoded before scanning. admin_whitelist lists the user_login values that
    are allowed to be administrators; any other login is flagged for review.
    """
    whitelist = {u.lower() for u in (admin_whitelist or [])}
    f = Findings()

    for match in _AUTOLOAD_ROW_RE.finditer(sql_text):
        name, value = match.group(1), match.group(2)

        if name == "cron":
            f.cron_present = True

        # Scope-connector family (precise — never matches wpsc_*).
        if _SC_NAME_RE.match(name):
            f.scope_connector_options.append(name)

        # MD5-hash-named autoloaded option: illegitimate by construction.
        if _MD5_NAME_RE.match(name):
            f.hash_named_options.append(name)

        # Literal code in the raw value.
        if any(rx.search(value) for rx in _CODE_MARKERS):
            f.autoloaded_code.append(name)

        # Decode base64 and re-scan for code + cloaking signatures.
        decoded = _decode_b64_blobs(value)
        if decoded:
            if any(rx.search(decoded) for rx in _CODE_MARKERS):
                f.autoloaded_code.append(name)
            if any(rx.search(decoded) for rx in _CLOAKING_MARKERS):
                f.cloaking_options.append(name)

    # Malicious cron hook / custom interval, wherever it is serialised.
    if _SC_CRON_HOOK in sql_text:
        f.malicious_cron.append(_SC_CRON_HOOK)
    if _SC_CRON_INTERVAL in sql_text:
        f.malicious_cron.append(_SC_CRON_INTERVAL)

    # Injected <script>/eval in any long-text column.
    f.injected_scripts = sum(len(rx.findall(sql_text)) for rx in _SCRIPT_MARKERS)

    # Spam keywords anywhere (usually wp_posts content).
    f.spam_posts = len(_SPAM_RE.findall(sql_text))

    # Application passwords live as user meta.
    if re.search(r"_application_passwords", sql_text):
        f.application_passwords = True

    # Best-effort: pull user_login values from wp_users INSERTs.
    for m in re.finditer(
        r"\(\s*\d+\s*,\s*'([^']+)'\s*,\s*'[^']*'\s*,\s*'[^']*'\s*,", sql_text
    ):
        f.admin_users.append(m.group(1))

    if whitelist:
        f.rogue_admins = [u for u in dict.fromkeys(f.admin_users) if u.lower() not in whitelist]

    # De-dupe every list.
    f.autoloaded_code = list(dict.fromkeys(f.autoloaded_code))
    f.scope_connector_options = list(dict.fromkeys(f.scope_connector_options))
    f.hash_named_options = list(dict.fromkeys(f.hash_named_options))
    f.cloaking_options = list(dict.fromkeys(f.cloaking_options))
    f.malicious_cron = list(dict.fromkeys(f.malicious_cron))
    f.admin_users = list(dict.fromkeys(f.admin_users))
    return f


def report(findings: Findings, *, dump_path: str) -> Report:
    rep = Report(title=f"Database scan — {dump_path}")
    for name in findings.cloaking_options:
        rep.add("Base64 CLOAKING injector (auto-remove)", f"wp_options: {name}")
    for name in findings.hash_named_options:
        rep.add("MD5-hash-named autoloaded option (auto-remove)", f"wp_options: {name}")
    for name in findings.scope_connector_options:
        rep.add("Scope-connector `sc_` family (auto-remove)", f"wp_options: {name}")
    for name in findings.autoloaded_code:
        rep.add("Autoloaded options with code (auto-remove)", f"wp_options: {name}")
    for hook in findings.malicious_cron:
        rep.add("Malicious cron (auto-purge)", hook)
    if findings.cron_present:
        rep.add("Cron in wp_options (auto-purge)", "cron")
    if findings.application_passwords:
        rep.add("Application passwords (auto-remove)", "_application_passwords meta present")
    for u in findings.rogue_admins:
        rep.add("Users NOT in admin whitelist (delete + reassign posts)", u)
    if findings.injected_scripts:
        rep.add("Injected scripts/eval (manual review)", f"{findings.injected_scripts} match(es)")
    if findings.spam_posts:
        rep.add("Spam keyword hits in content (manual review)", f"{findings.spam_posts} hit(s)")
    return rep


# --------------------------------------------------------------------------
# Remote operations (SSH/WP-CLI). Writes are dry-run guarded by Remote.
# --------------------------------------------------------------------------


def export_source(remote: Remote, local_dump: str) -> str:
    """Export the source DB and pull it to `local_dump`. Read-only on source."""
    remote.check_connectivity()
    remote_dump = f"{remote.host.path.rstrip('/')}/mb-rebuild-export.sql"
    # Export is a read of the DB; we still create a file on the source, so it
    # is gated as a write and cleaned up afterwards.
    remote.wp(["db", "export", remote_dump, "--add-drop-table"], write=True)
    scp_pull(remote.host, remote_dump, local_dump, dry_run=remote.dry_run)
    remote.run(["rm", "-f", remote_dump], write=True, check=False)
    if not remote.dry_run:
        ok(f"exported source DB -> {local_dump}")
    return local_dump


def import_and_clean(
    remote: Remote,
    local_dump: str,
    findings: Findings,
    *,
    admin_whitelist: list[str],
    remove_users: bool,
    reassign_to: str = "1",
    search_replace: list[tuple[str, str]] | None = None,
) -> None:
    """Import the (validated) dump into the target and auto-remediate.

    All remote writes honour Remote.dry_run. Content-level spam is left for
    manual review — this function never rewrites wp_posts.
    """
    # 1. Import.
    remote_tmp = f"{remote.host.path.rstrip('/')}/mb-rebuild-import.sql"
    scp_push(remote.host, local_dump, remote_tmp, dry_run=remote.dry_run)
    remote.wp(["db", "import", remote_tmp], write=True)
    remote.run(["rm", "-f", remote_tmp], write=True, check=False)

    # 2. Purge cron stored in options (covers sc_cron_fetch too).
    if findings.cron_present or findings.malicious_cron:
        remote.wp(["option", "delete", "cron"], write=True, check=False)

    # 3. Remove every flagged autoloaded option (code / sc_ / hash / cloaking).
    for name in findings.options_to_delete:
        remote.wp(["option", "delete", name], write=True, check=False)

    # 4. Remove application passwords for every user.
    if findings.application_passwords:
        remote.wp(
            ["user", "application-password", "delete", "--all-users", "--all"],
            write=True,
            check=False,
        )

    # 5. Rogue admins — delete WITH usermeta (wp handles it) and REASSIGN their
    #    posts to a legitimate account, so nothing is orphaned. Destructive, so
    #    opt-in via --remove-users.
    if remove_users and findings.rogue_admins:
        for login in findings.rogue_admins:
            if login.lower() in {u.lower() for u in admin_whitelist}:
                continue
            remote.wp(
                ["user", "delete", login, f"--reassign={reassign_to}", "--yes"],
                write=True,
                check=False,
            )
    elif findings.rogue_admins:
        warn(
            "rogue admins detected but --remove-users not set; "
            f"review manually: {', '.join(findings.rogue_admins)}"
        )

    # 6. Domain rewrite — serialization-safe (Elementor stores serialized data,
    #    so a raw SQL replace would corrupt it). This is what makes the site
    #    load on the new domain instead of the old one.
    for old, new in search_replace or []:
        remote.wp(
            [
                "search-replace", old, new,
                "--all-tables", "--precise", "--recurse-objects", "--skip-columns=guid",
            ],
            write=True,
            check=False,
        )
    if search_replace:
        remote.wp(["cache", "flush"], write=True, check=False)
        remote.wp(["rewrite", "flush"], write=True, check=False)

    if remote.dry_run:
        dry("database import + remediation planned (dry-run)")
    else:
        ok("database imported and remediated")
