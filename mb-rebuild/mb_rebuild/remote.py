"""SSH + WP-CLI execution against a remote host.

Design rules honoured here:
  * The tool runs on the operator's machine. It NEVER uploads or leaves a
    script on the server; it only runs individual `wp` / shell commands
    over SSH (and copies files with scp/rsync).
  * Every write goes through Remote.run(..., write=True), which is a no-op
    that only logs the command when dry_run is set.
  * Commands are passed as argv lists and shell-quoted locally, so remote
    arguments are never interpolated into a shell string unescaped.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any, Sequence

from .utils import MbError, dry, info, redact


@dataclass
class Host:
    """A target/source host addressable over SSH.

    spec forms accepted by Host.parse():
        user@example.com:/var/www/site
        user@example.com                 (path defaults to ~)
        example.com:/var/www/site        (user defaults to ssh config)
    An optional port may be given separately.
    """

    host: str
    user: str | None = None
    path: str = "~"
    port: int | None = None
    ssh_opts: tuple[str, ...] = ()

    @classmethod
    def parse(cls, spec: str, *, port: int | None = None) -> "Host":
        if not spec:
            raise MbError("empty host specification")
        user = None
        rest = spec
        if "@" in rest:
            user, rest = rest.split("@", 1)
        host, sep, path = rest.partition(":")
        return cls(host=host, user=user, path=path if sep else "~", port=port)

    @property
    def target(self) -> str:
        return f"{self.user}@{self.host}" if self.user else self.host


class Remote:
    """Runs commands on a Host. In dry-run, writes are logged not executed."""

    def __init__(self, host: Host, *, dry_run: bool = True, timeout: int = 300):
        self.host = host
        self.dry_run = dry_run
        self.timeout = timeout

    # -- low level ---------------------------------------------------------

    def _ssh_argv(self, remote_cmd: str) -> list[str]:
        argv = ["ssh", "-o", "BatchMode=yes"]
        if self.host.port:
            argv += ["-p", str(self.host.port)]
        argv += list(self.host.ssh_opts)
        argv += [self.host.target, remote_cmd]
        return argv

    def run(
        self,
        argv: Sequence[str],
        *,
        write: bool = False,
        cwd: str | None = None,
        check: bool = True,
        capture: bool = True,
    ) -> subprocess.CompletedProcess | None:
        """Run a command on the remote host.

        argv is the remote command as an argv list. It is shell-quoted once
        so the remote shell receives exact arguments. If cwd is given the
        command runs inside that directory. When write=True and dry_run is
        active, the command is logged and skipped (returns None).
        """
        remote_cmd = shlex.join(argv)
        if cwd:
            remote_cmd = f"cd {shlex.quote(cwd)} && {remote_cmd}"

        if write and self.dry_run:
            dry(f"ssh {self.host.target}: {redact(remote_cmd)}")
            return None

        full = self._ssh_argv(remote_cmd)
        try:
            proc = subprocess.run(
                full,
                capture_output=capture,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise MbError("ssh not found on PATH — install OpenSSH client") from exc
        except subprocess.TimeoutExpired as exc:
            raise MbError(f"remote command timed out after {self.timeout}s") from exc

        if check and proc.returncode != 0:
            detail = redact((proc.stderr or proc.stdout or "").strip())
            raise MbError(
                f"remote command failed (exit {proc.returncode}) on "
                f"{self.host.target}: {redact(remote_cmd)}\n{detail}"
            )
        return proc

    # -- WP-CLI convenience ------------------------------------------------

    def wp(self, args: Sequence[str], *, write: bool = False, check: bool = True):
        """Run `wp <args> --path=<host.path>` on the remote host."""
        argv = ["wp", *args, f"--path={self.host.path}"]
        return self.run(argv, write=write, check=check)

    def wp_json(self, args: Sequence[str]) -> Any:
        """Run a read-only wp command that emits JSON and parse it.

        Read-only, so it executes even in dry-run (detection must work).
        """
        proc = self.wp(args, write=False, check=True)
        if proc is None:  # pragma: no cover - reads never dry-skip
            return None
        text = (proc.stdout or "").strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise MbError(f"expected JSON from `wp {shlex.join(args)}`: {exc}") from exc

    def check_connectivity(self) -> None:
        """Verify SSH + WP-CLI are reachable.

        In dry-run this is advisory: a plan can legitimately be previewed
        before the target host exists, so an unreachable host only warns.
        With --apply it fails fast, because the writes that follow require it.
        """
        try:
            proc = self.run(["wp", "--version", f"--path={self.host.path}"], check=False)
        except MbError as exc:
            # e.g. the ssh client is not installed at all.
            if self.dry_run:
                from .utils import warn

                warn(f"{exc}  [dry-run: continuing to show the plan]")
                return
            raise
        if proc is None or proc.returncode != 0:
            hint = redact((proc.stderr or "").strip()) if proc else ""
            msg = (
                f"cannot reach WP-CLI on {self.host.target} "
                f"(path={self.host.path}). {hint}".strip()
            )
            if self.dry_run:
                from .utils import warn

                warn(msg + "  [dry-run: continuing to show the plan]")
                return
            raise MbError(msg)
        info(f"connected: {self.host.target} — {(proc.stdout or '').strip()}")


def scp_pull(host: Host, remote_path: str, local_path: str, *, dry_run: bool) -> None:
    """Copy a file FROM the remote host to the local machine."""
    src = f"{host.target}:{remote_path}"
    if dry_run:
        dry(f"scp {src} -> {local_path}")
        return
    argv = ["scp", "-o", "BatchMode=yes"]
    if host.port:
        argv += ["-P", str(host.port)]
    argv += [src, local_path]
    _run_local(argv, "scp")


def scp_push(host: Host, local_path: str, remote_path: str, *, dry_run: bool) -> None:
    """Copy a file FROM the local machine TO the remote host."""
    dst = f"{host.target}:{remote_path}"
    if dry_run:
        dry(f"scp {local_path} -> {dst}")
        return
    argv = ["scp", "-o", "BatchMode=yes"]
    if host.port:
        argv += ["-P", str(host.port)]
    argv += [local_path, dst]
    _run_local(argv, "scp")


def rsync_pull(host: Host, remote_dir: str, local_dir: str, *, dry_run: bool) -> None:
    """Mirror a directory FROM the remote host to the local machine."""
    src = f"{host.target}:{remote_dir.rstrip('/')}/"
    if dry_run:
        dry(f"rsync -a {src} -> {local_dir}")
        return
    ssh = "ssh -o BatchMode=yes" + (f" -p {host.port}" if host.port else "")
    argv = ["rsync", "-a", "-e", ssh, src, local_dir]
    _run_local(argv, "rsync")


def _run_local(argv: list[str], name: str) -> None:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise MbError(f"{name} not found on PATH") from exc
    if proc.returncode != 0:
        raise MbError(f"{name} failed: {redact((proc.stderr or '').strip())}")
