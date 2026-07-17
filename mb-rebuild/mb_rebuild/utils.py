"""Shared helpers: logging, dry-run guarding, secret redaction, YAML I/O.

Kept dependency-light on purpose (stdlib + PyYAML) so the tool stays easy
to run on an operator's machine without a heavy environment.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any

import yaml

# --------------------------------------------------------------------------
# Colour-free, prefix-based logging. We avoid a logging framework so output
# stays readable in a plain terminal and is trivial to capture in reports.
# --------------------------------------------------------------------------

_QUIET = False


def set_quiet(quiet: bool) -> None:
    global _QUIET
    _QUIET = quiet


def _emit(prefix: str, msg: str, *, err: bool = False) -> None:
    # Resolve the stream at call time (not import time) so capsys and any
    # stdout/stderr redirection see the output.
    stream = sys.stderr if err else sys.stdout
    if _QUIET and not err:
        return
    print(f"{prefix} {msg}", file=stream)


def info(msg: str) -> None:
    _emit("[*]", msg)


def ok(msg: str) -> None:
    _emit("[+]", msg)


def warn(msg: str) -> None:
    _emit("[!]", msg, err=True)


def error(msg: str) -> None:
    _emit("[x]", msg, err=True)


def step(msg: str) -> None:
    _emit("==>", msg)


def dry(msg: str) -> None:
    """Log an action that WOULD run but is skipped because of dry-run."""
    _emit("[dry-run]", msg)


class MbError(Exception):
    """User-facing error. The CLI prints the message without a traceback."""


# --------------------------------------------------------------------------
# Secret redaction. Licence keys, DB passwords and salts must never leak
# into logs or reports. Everything user-facing runs through redact().
# --------------------------------------------------------------------------

# Order matters: longer / more specific patterns first.
_SECRET_PATTERNS = [
    re.compile(r"(--?(?:license|licence|key|token|secret|password|pass|pwd)[= ])(\S+)", re.I),
    re.compile(r"((?:DB_PASSWORD|AUTH_KEY|SECURE_AUTH_KEY|LOGGED_IN_KEY|NONCE_KEY)\s*[:=]\s*)(\S+)", re.I),
    re.compile(r"(://[^:/@\s]+:)([^@/\s]+)(@)"),  # user:pass@host
]

# Exact secret VALUES the tool has resolved (licence keys, DB passwords).
# Because we know the literal string, we can mask it regardless of where it
# appears in a command — including positional args like
# `wp <plugin> license activate <KEY>`, which the flag patterns above miss.
_KNOWN_SECRETS: set[str] = set()


def register_secret(value: str | None) -> None:
    """Remember a secret literal so redact() masks it anywhere it appears."""
    if value and len(value) >= 4:  # ignore trivially short / empty values
        _KNOWN_SECRETS.add(value)


def redact(text: str) -> str:
    """Mask anything that looks like a credential in a string."""
    if not text:
        return text
    out = text
    # Known literals first — the most reliable masking.
    for secret in _KNOWN_SECRETS:
        if secret in out:
            out = out.replace(secret, "***")
    out = _SECRET_PATTERNS[0].sub(lambda m: f"{m.group(1)}***", out)
    out = _SECRET_PATTERNS[1].sub(lambda m: f"{m.group(1)}***", out)
    out = _SECRET_PATTERNS[2].sub(lambda m: f"{m.group(1)}***{m.group(3)}", out)
    return out


# --------------------------------------------------------------------------
# .env loading. The catalogue never stores licence values, only the *name*
# of the env var that holds them. We read those names' values from a .env
# file (git-ignored) or the process environment.
# --------------------------------------------------------------------------


def load_env_file(path: str | None) -> dict[str, str]:
    """Parse a minimal KEY=VALUE .env file. Missing file -> empty dict.

    Lines starting with '#' and blank lines are ignored. Values may be
    optionally quoted. This intentionally does NOT mutate os.environ.
    """
    env: dict[str, str] = {}
    if not path or not os.path.exists(path):
        return env
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key:
                env[key] = val
    return env


def resolve_secret(var_name: str, env_file: dict[str, str]) -> str | None:
    """Look up a secret by env-var name: .env file wins, then os.environ."""
    if var_name in env_file:
        return env_file[var_name]
    return os.environ.get(var_name)


# --------------------------------------------------------------------------
# YAML helpers with friendly errors.
# --------------------------------------------------------------------------


def read_yaml(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        raise MbError(f"file not found: {path}")
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        raise MbError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise MbError(f"expected a mapping at the top level of {path}")
    return data


def write_yaml(path: str, data: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, default_flow_style=False, allow_unicode=True)


@dataclass
class Report:
    """Accumulates findings/actions for a run, rendered at the end."""

    title: str
    sections: dict[str, list[str]] = field(default_factory=dict)

    def add(self, section: str, line: str) -> None:
        self.sections.setdefault(section, []).append(line)

    def is_empty(self) -> bool:
        return not any(self.sections.values())

    def render(self) -> str:
        lines = [f"# {self.title}", ""]
        if self.is_empty():
            lines.append("_Nothing to report._")
            return "\n".join(lines)
        for section, items in self.sections.items():
            lines.append(f"## {section}")
            for item in items:
                lines.append(f"- {redact(item)}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"
