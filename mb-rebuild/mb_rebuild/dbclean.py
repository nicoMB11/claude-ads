"""Module 3 — the database: export, scan, clean, import.

The database is the black hole of every WordPress clean-up. Files get all
the attention while the re-infector is often an autoloaded wp_options row
that runs on every page load. This module treats the DB with the same rigour
as the filesystem.

Flow:
  1. export the source DB over SSH (`wp db export`)
  2. store it locally, timestamped, as a snapshot
  3. SCAN the dump for infection markers (pure, testable — see scan_dump)
  4. produce a report for operator validation
  5. import into the target, then run WP-CLI remediation for the categories
     that are safe to auto-fix (rogue admins, cron, app passwords,
     code-bearing autoloaded options). Content-level spam in wp_posts is
     reported for manual review, never silently rewritten (it could damage
     the design we are trying to preserve).
"""

from __future__ import annotations

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


@dataclass
class Findings:
    autoloaded_code: list[str] = field(default_factory=list)
    injected_scripts: int = 0
    spam_posts: int = 0
    application_passwords: bool = False
    admin_users: list[str] = field(default_factory=list)
    rogue_admins: list[str] = field(default_factory=list)
    cron_present: bool = False

    def any(self) -> bool:
        return bool(
            self.autoloaded_code
            or self.injected_scripts
            or self.spam_posts
            or self.application_passwords
            or self.rogue_admins
            or self.cron_present
        )


def scan_dump(sql_text: str, admin_whitelist: list[str] | None = None) -> Findings:
    """Statically scan a SQL dump for infection markers.

    Pure function — no I/O — so it is unit-testable. admin_whitelist lists
    the user_login values that are allowed to be administrators; any other
    admin found is reported as rogue.
    """
    whitelist = {u.lower() for u in (admin_whitelist or [])}
    f = Findings()

    # Autoloaded options carrying code are the classic re-infector.
    for match in _AUTOLOAD_ROW_RE.finditer(sql_text):
        name, value = match.group(1), match.group(2)
        if name == "cron":
            f.cron_present = True
        if any(rx.search(value) for rx in _CODE_MARKERS):
            f.autoloaded_code.append(name)

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
        login = m.group(1)
        f.admin_users.append(login)

    # We cannot reliably bind login->role from text alone, so treat any user
    # not in the whitelist as a candidate rogue admin for operator review.
    if whitelist:
        f.rogue_admins = [u for u in dict.fromkeys(f.admin_users) if u.lower() not in whitelist]

    # De-dupe.
    f.autoloaded_code = list(dict.fromkeys(f.autoloaded_code))
    f.admin_users = list(dict.fromkeys(f.admin_users))
    return f


def report(findings: Findings, *, dump_path: str) -> Report:
    rep = Report(title=f"Database scan — {dump_path}")
    for name in findings.autoloaded_code:
        rep.add("Autoloaded options with code (auto-remove)", f"wp_options: {name}")
    if findings.cron_present:
        rep.add("Cron in wp_options (auto-purge)", "cron")
    if findings.application_passwords:
        rep.add("Application passwords (auto-remove)", "_application_passwords meta present")
    for u in findings.rogue_admins:
        rep.add("Users NOT in admin whitelist (review / delete)", u)
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

    # 2. Purge cron stored in options.
    if findings.cron_present:
        remote.wp(["option", "delete", "cron"], write=True, check=False)

    # 3. Remove code-bearing autoloaded options.
    for name in findings.autoloaded_code:
        remote.wp(["option", "delete", name], write=True, check=False)

    # 4. Remove application passwords for every user.
    if findings.application_passwords:
        remote.wp(
            ["user", "application-password", "delete", "--all-users", "--all"],
            write=True,
            check=False,
        )

    # 5. Rogue admins — only if the operator opted in (destructive).
    if remove_users and findings.rogue_admins:
        for login in findings.rogue_admins:
            if login.lower() in {u.lower() for u in admin_whitelist}:
                continue
            remote.wp(
                ["user", "delete", login, "--reassign=1", "--yes"],
                write=True,
                check=False,
            )
    elif findings.rogue_admins:
        warn(
            "rogue admins detected but --remove-users not set; "
            f"review manually: {', '.join(findings.rogue_admins)}"
        )

    if remote.dry_run:
        dry("database import + remediation planned (dry-run)")
    else:
        ok("database imported and remediated")
