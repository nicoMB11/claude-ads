#!/usr/bin/env python3
"""mb-remediation — outillage de remédiation WordPress multi-sites via SSH.

Tourne SUR TA MACHINE. Pilote les sites en SSH + WP-CLI. Ne dépose RIEN sur le
serveur (aucun fichier PHP posé dans l'arbo — ce serait un webshell).

Ordre de construction imposé par le runbook :
  backup (module 0) -> modules lecture seule -> clean (module 7, en dernier).

Garde-fous non contournables :
  * `clean` REFUSE de démarrer si aucun snapshot vérifié n'existe pour le site.
  * `--dry-run` par défaut ; `--execute` obligatoire pour toute action destructive.
  * `--site` obligatoire en mode destructif (jamais les 25 d'un coup).
  * `restore --full` REFUSE de partir d'un snapshot INFECTE.
  * Snapshots JAMAIS écrits sur l'hébergement. Aucun secret en dur.
  * Log horodaté exhaustif (alimente le journal d'incident).

Usage :
    python3 mb_remediation.py <commande> [options]

Commandes :
    inventory     Version WP/PHP, extensions, thèmes, comptes admin (lecture seule)
    checksums     wp core/plugin verify-checksums (lecture seule)
    signatures    Patterns de malware + décodage des timestamps Unix (lecture seule)
    persistence   mu-plugins, cron, comptes+trous d'ID, App Passwords, .htaccess… (lecture seule)
    report        Checklist Annexe A par site, Markdown + JSON (lecture seule)
    backup        Snapshot fichiers + BDD + manifeste SHA-256 + métadonnées (module 0)
    verify        Vérifie l'intégrité d'un snapshot
    diff          Compare l'état actuel d'un site à un snapshot
    restore       Restauration chirurgicale (--file / --db-table) ou --full (gardée)
    clean         Suppression des artefacts (--dry-run par défaut, gardé par backup)

Dépendances : paramiko, PyYAML  (voir requirements.txt)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import posixpath
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("Dépendance manquante : PyYAML. Installe avec `pip install -r requirements.txt`.")

try:
    import paramiko
except ImportError:  # pragma: no cover
    paramiko = None  # toléré pour les commandes hors-ligne (verify, help)


# --------------------------------------------------------------------------- #
# Constantes                                                                    #
# --------------------------------------------------------------------------- #

STATUS_INFECTED = "INFECTE"
STATUS_INPROGRESS = "ENCOURS"
STATUS_VERIFIED = "VERIFIE"
VALID_STATUSES = (STATUS_INFECTED, STATUS_INPROGRESS, STATUS_VERIFIED)

# Signatures de fichiers (Annexe B). Regex appliqués au nom de fichier (basename).
FILE_SIGNATURES = [
    r"^Liar-Console\.php$",
    r"_\d{10}\.php$",                 # tout .php suffixé d'un timestamp Unix
    r"^category_template_.*",
    r"^custom[_-]file.*",
    r"^custom-functions-.*",
    r"^search-template-.*",
    r"^front-page-template-.*",
    r"^error-404-.*",
    r"^widget-area-.*",
    r"^config-\d+.*",
    r"^(bottom|top|home|archives|post|comment_section)[-_].*\.php$",
]

# Marqueurs de code obfusqué (Annexe B).
CODE_SIGNATURES = [
    "eval(", "base64_decode", "gzinflate", "str_rot13", "assert(",
    "create_function", "FilesMan", "preg_replace",  # /e affiné plus bas
]

# Regex pour extraire un timestamp Unix (10 chiffres, ère 2001-2033) d'un nom.
TS_RE = re.compile(r"(?<!\d)(1[0-9]{9})(?!\d)")

# Checklist Annexe A (miroir de l'appli de suivi).
ANNEXE_A = [
    ("core_checksums", "wp core verify-checksums → OK"),
    ("plugin_checksums", "wp plugin verify-checksums --all → OK"),
    ("premium_diff", "Extensions premium : diff ZIP officiel → OK (manuel)"),
    ("no_unknown_php", "Aucun .php inconnu (racine, wp-content, uploads, themes)"),
    ("no_generated_theme", "Aucun dossier de thème à nom généré"),
    ("mu_plugins_clean", "mu-plugins/ vide ou 100 % légitime et relu"),
    ("no_rogue_admin", "Aucun compte admin non reconnu, aucun trou d'ID"),
    ("no_app_passwords", "Aucune Application Password active"),
    ("cron_clean", "Tâches cron : uniquement des hooks légitimes"),
    ("functions_clean", "functions.php du thème actif : aucun marqueur d'obfuscation"),
    ("htaccess_clean", ".htaccess : aucune redirection inconnue"),
    ("secrets_rotated", "Salts régénérés, mots de passe admin + DB changés (manuel)"),
    ("wordfence_clean", "Scan Wordfence complet : 0 alerte (manuel)"),
    ("infomaniak_clean", "Scan Infomaniak : 0 menace (manuel)"),
    ("no_spam_indexed", "Aucune page de spam indexée (manuel)"),
]


# --------------------------------------------------------------------------- #
# Utilitaires                                                                   #
# --------------------------------------------------------------------------- #

def now_utc() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def ts_slug(dt: Optional[_dt.datetime] = None) -> str:
    return (dt or now_utc()).strftime("%Y-%m-%d_%H-%M-%S")


def human(msg: str, kind: str = "info") -> None:
    colors = {"info": "", "ok": "\033[32m", "warn": "\033[33m", "err": "\033[31m", "step": "\033[36m"}
    reset = "\033[0m" if sys.stdout.isatty() else ""
    prefix = colors.get(kind, "") if sys.stdout.isatty() else ""
    print(f"{prefix}{msg}{reset}")


def unix_ts_to_date(ts: int) -> str:
    try:
        return _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return "?"


# --------------------------------------------------------------------------- #
# Journal d'incident (log horodaté JSONL)                                       #
# --------------------------------------------------------------------------- #

class IncidentLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, **fields: Any) -> None:
        record = {"ts": now_utc().isoformat(), "event": event, **fields}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# Config                                                                        #
# --------------------------------------------------------------------------- #

@dataclass
class Site:
    name: str
    path: str
    category: str = "?"
    url: str = ""


@dataclass
class Config:
    host: str
    port: int
    user: str
    ssh_key_path: Optional[str]
    ssh_key_passphrase_env: Optional[str]
    backup_dir: Path
    operator: str
    wp_bin: str
    sites: list[Site] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "Config":
        if not path.exists():
            sys.exit(f"Config introuvable : {path}\n"
                     f"Copie sites.example.yaml en {path.name} et remplis-le.")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        ssh = data.get("ssh", {})
        sites = [Site(name=str(s["name"]), path=str(s["path"]),
                      category=str(s.get("category", "?")), url=str(s.get("url", "")))
                 for s in data.get("sites", [])]
        if not sites:
            sys.exit("Aucun site défini dans la config.")
        return cls(
            host=ssh.get("host", ""),
            port=int(ssh.get("port", 22)),
            user=ssh.get("user", ""),
            ssh_key_path=ssh.get("ssh_key_path") or None,
            ssh_key_passphrase_env=ssh.get("ssh_key_passphrase_env") or None,
            backup_dir=Path(os.path.expanduser(str(data.get("backup_dir", "~/mb-backups")))),
            operator=str(data.get("operator", os.environ.get("USER", "?"))),
            wp_bin=str(data.get("wp_bin", "wp")),
            sites=sites,
        )

    def select(self, names: Optional[list[str]], use_all: bool) -> list[Site]:
        if use_all:
            return list(self.sites)
        if not names:
            return []
        by_name = {s.name: s for s in self.sites}
        chosen, missing = [], []
        for n in names:
            (chosen.append(by_name[n]) if n in by_name else missing.append(n))
        if missing:
            sys.exit(f"Site(s) inconnu(s) dans la config : {', '.join(missing)}")
        return chosen


# --------------------------------------------------------------------------- #
# Couche SSH                                                                    #
# --------------------------------------------------------------------------- #

class SSH:
    """Enveloppe paramiko minimale. Aucun secret en dur : clé ou agent."""

    def __init__(self, cfg: Config):
        if paramiko is None:
            sys.exit("Dépendance manquante : paramiko. `pip install -r requirements.txt`.")
        self.cfg = cfg
        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(paramiko.RejectPolicy())

    def __enter__(self) -> "SSH":
        passphrase = None
        if self.cfg.ssh_key_passphrase_env:
            passphrase = os.environ.get(self.cfg.ssh_key_passphrase_env)
        key_filename = (os.path.expanduser(self.cfg.ssh_key_path)
                        if self.cfg.ssh_key_path else None)
        self.client.connect(
            hostname=self.cfg.host, port=self.cfg.port, username=self.cfg.user,
            key_filename=key_filename, passphrase=passphrase,
            look_for_keys=True, allow_agent=True, timeout=30,
        )
        return self

    def __exit__(self, *exc: Any) -> None:
        self.client.close()

    def run(self, command: str, check: bool = False) -> tuple[int, str, str]:
        stdin, stdout, stderr = self.client.exec_command(command, timeout=600)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        rc = stdout.channel.recv_exit_status()
        if check and rc != 0:
            raise RuntimeError(f"Commande échouée (rc={rc}) : {command}\n{err.strip()}")
        return rc, out, err

    def wp(self, site: Site, args: str, check: bool = False) -> tuple[int, str, str]:
        cmd = (f"{shlex.quote(self.cfg.wp_bin)} --path={shlex.quote(site.path)} "
               f"--skip-themes --skip-plugins {args}")
        return self.run(cmd, check=check)

    def download_stream(self, remote_command: str, dest: Path) -> int:
        """Exécute une commande distante et écrit sa sortie binaire dans `dest`."""
        stdin, stdout, stderr = self.client.exec_command(remote_command, timeout=3600)
        written = 0
        with dest.open("wb") as fh:
            chan = stdout.channel
            while True:
                data = chan.recv(65536)
                if not data:
                    if chan.exit_status_ready() and chan.recv_ready() is False:
                        break
                    if chan.closed:
                        break
                    continue
                fh.write(data)
                written += len(data)
        rc = stdout.channel.recv_exit_status()
        if rc != 0:
            err = stderr.read().decode("utf-8", "replace")
            raise RuntimeError(f"Stream distant échoué (rc={rc}): {remote_command}\n{err.strip()}")
        return written


# --------------------------------------------------------------------------- #
# Snapshots (module 0 : backup / verify / diff / restore)                       #
# --------------------------------------------------------------------------- #

class SnapshotStore:
    def __init__(self, cfg: Config, log: IncidentLog):
        self.cfg = cfg
        self.log = log
        cfg.backup_dir.mkdir(parents=True, exist_ok=True)

    def dir_for(self, site: Site, status: str, dt: _dt.datetime) -> Path:
        return self.cfg.backup_dir / f"{ts_slug(dt)}_{site.name}_{status}"

    def list_for(self, site_name: str) -> list[Path]:
        """Snapshots d'un site, triés par nom (donc chronologiquement).

        Nom de dossier : <YYYY-MM-DD>_<HH-MM-SS>_<site>_<STATUS>.
        """
        if not self.cfg.backup_dir.exists():
            return []
        pat = re.compile(
            r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_"
            + re.escape(site_name)
            + r"_(" + "|".join(VALID_STATUSES) + r")$")
        return sorted(p for p in self.cfg.backup_dir.iterdir()
                      if p.is_dir() and pat.match(p.name))

    # ---- backup ----
    def backup(self, ssh: SSH, site: Site, status: str, command: str,
               dry_run: bool) -> Optional[Path]:
        if status not in VALID_STATUSES:
            sys.exit(f"Statut invalide : {status}. Attendu : {', '.join(VALID_STATUSES)}")
        dt = now_utc()
        dest = self.dir_for(site, status, dt)
        if dry_run:
            human(f"  [dry-run] snapshot {status} de {site.name} → {dest}", "warn")
            return None
        dest.mkdir(parents=True, exist_ok=True)
        qpath = shlex.quote(site.path)

        # 1) fichiers (tar.gz streamé)
        human(f"  → archive fichiers…", "step")
        files_tar = dest / "files.tar.gz"
        nbytes = ssh.download_stream(f"tar czf - -C {qpath} .", files_tar)

        # 2) manifeste SHA-256 (calculé côté serveur)
        human(f"  → manifeste SHA-256…", "step")
        rc, out, err = ssh.run(
            f"cd {qpath} && find . -type f -print0 | xargs -0 sha256sum 2>/dev/null")
        manifest = {}
        for line in out.splitlines():
            if "  " in line:
                h, f = line.split("  ", 1)
                manifest[f] = h
        (dest / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=0), encoding="utf-8")

        # 3) base de données
        human(f"  → export base de données…", "step")
        db_sql = dest / "db.sql"
        ssh.download_stream(
            f"{shlex.quote(self.cfg.wp_bin)} --path={qpath} db export - "
            f"--single-transaction --skip-lock-tables", db_sql)

        # 4) métadonnées
        rc, wpver, _ = ssh.wp(site, "core version")
        meta = {
            "site": site.name, "path": site.path, "category": site.category,
            "status": status, "created": dt.isoformat(),
            "wp_version": wpver.strip() or "?", "operator": self.cfg.operator,
            "command": command, "files_bytes": nbytes,
            "manifest_count": len(manifest),
        }
        (dest / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        self.log.write("backup", site=site.name, status=status, dest=str(dest),
                       files_bytes=nbytes, manifest_count=len(manifest))
        human(f"  ✓ snapshot {status} : {dest.name} "
              f"({nbytes/1e6:.1f} Mo, {len(manifest)} fichiers)", "ok")

        ok, problems = self.verify(dest)
        if not ok:
            human(f"  ⚠ snapshot NON vérifié : {'; '.join(problems)}", "err")
        return dest

    # ---- verify ----
    def verify(self, snap: Path) -> tuple[bool, list[str]]:
        problems: list[str] = []
        files_tar = snap / "files.tar.gz"
        db_sql = snap / "db.sql"
        manifest_p = snap / "manifest.json"

        if not files_tar.exists() or files_tar.stat().st_size == 0:
            problems.append("archive fichiers manquante ou vide")
        else:
            import tarfile
            try:
                with tarfile.open(files_tar, "r:gz") as tf:
                    n_in_tar = sum(1 for m in tf if m.isfile())
            except Exception as e:  # noqa: BLE001
                problems.append(f"archive illisible ({e})")
                n_in_tar = -1
            if manifest_p.exists() and n_in_tar >= 0:
                n_manifest = len(json.loads(manifest_p.read_text(encoding="utf-8")))
                # tolérance : le manifeste peut compter quelques fichiers de plus/moins
                if abs(n_manifest - n_in_tar) > max(5, int(0.02 * max(n_manifest, 1))):
                    problems.append(f"écart manifeste/archive ({n_manifest} vs {n_in_tar})")

        if not db_sql.exists() or db_sql.stat().st_size == 0:
            problems.append("dump SQL manquant ou vide")
        else:
            tail = db_sql.read_bytes()[-4096:].decode("utf-8", "replace").lower()
            if "dump completed" not in tail and "-- done" not in tail and \
               not tail.rstrip().endswith(";"):
                problems.append("dump SQL possiblement tronqué (fin inattendue)")

        return (not problems, problems)

    # ---- helper : dernier snapshot vérifié ----
    def latest_verified_backup(self, site_name: str) -> Optional[Path]:
        for snap in reversed(self.list_for(site_name)):
            ok, _ = self.verify(snap)
            if ok:
                return snap
        return None


# --------------------------------------------------------------------------- #
# Modules lecture seule                                                          #
# --------------------------------------------------------------------------- #

def _json_wp(ssh: SSH, site: Site, args: str) -> Any:
    rc, out, err = ssh.wp(site, f"{args} --format=json")
    if rc != 0 or not out.strip():
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def module_inventory(ssh: SSH, site: Site) -> dict:
    rc, core, _ = ssh.wp(site, "core version")
    rc, php, _ = ssh.run("php -v 2>/dev/null | head -1")
    plugins = _json_wp(ssh, site, "plugin list --fields=name,status,version,update") or []
    themes = _json_wp(ssh, site, "theme list --fields=name,status,version") or []
    users = _json_wp(ssh, site, "user list --role=administrator "
                                "--fields=ID,user_login,user_email,user_registered") or []
    return {
        "site": site.name, "category": site.category,
        "wp_version": core.strip() or "?",
        "php_version": (php.strip() or "?"),
        "plugins": plugins, "plugins_count": len(plugins),
        "themes": themes, "themes_count": len(themes),
        "admins": users, "admins_count": len(users),
    }


def module_checksums(ssh: SSH, site: Site) -> dict:
    rc_core, core_out, core_err = ssh.wp(site, "core verify-checksums")
    rc_plug, plug_out, plug_err = ssh.wp(site, "plugin verify-checksums --all")
    core_issues = [l for l in (core_out + core_err).splitlines()
                   if "Warning" in l or "does not verify" in l or "should not exist" in l]
    plug_issues = [l for l in (plug_out + plug_err).splitlines()
                   if "Warning" in l or "does not verify" in l or "checksums do not" in l
                   or "File was added" in l or "File was modified" in l]
    return {
        "site": site.name,
        "core_ok": rc_core == 0 and not core_issues,
        "core_issues": core_issues,
        "plugins_ok": rc_plug == 0 and not plug_issues,
        "plugin_issues": plug_issues,
    }


def module_signatures(ssh: SSH, site: Site) -> dict:
    qpath = shlex.quote(site.path)
    # liste des fichiers suspects (noms), + tout .php sous uploads
    rc, out, _ = ssh.run(
        f"find {qpath} \\( -name '*.php' -o -name '*.phtml' -o -name '*.suspected' \\) "
        f"-type f 2>/dev/null")
    all_php = [l for l in out.splitlines() if l.strip()]
    flagged_files = []
    for f in all_php:
        base = posixpath.basename(f)
        matched = [pat for pat in FILE_SIGNATURES if re.search(pat, base)]
        in_uploads = "/uploads/" in f  # un .php dans uploads est toujours suspect
        if matched or in_uploads:
            entry: dict[str, Any] = {"path": f, "reason": "nom" if matched else "php_dans_uploads"}
            m = TS_RE.search(base)
            if m:
                ts = int(m.group(1))
                entry["timestamp"] = ts
                entry["date"] = unix_ts_to_date(ts)
            flagged_files.append(entry)

    # dossiers de thème à nom généré (<mot>-<timestamp>)
    rc, tout, _ = ssh.run(
        f"find {qpath}/wp-content/themes -maxdepth 1 -type d 2>/dev/null")
    generated_themes = []
    for d in tout.splitlines():
        base = posixpath.basename(d)
        m = TS_RE.search(base)
        if m:
            generated_themes.append({"path": d, "timestamp": int(m.group(1)),
                                     "date": unix_ts_to_date(int(m.group(1)))})

    # grep de marqueurs d'obfuscation dans les .php (léger : -l, limité)
    patterns = "|".join(re.escape(s) for s in ["eval(", "base64_decode", "gzinflate",
                                               "str_rot13", "FilesMan", "create_function"])
    rc, gout, _ = ssh.run(
        f"grep -rlE {shlex.quote(patterns)} {qpath}/wp-content --include='*.php' 2>/dev/null | head -200")
    obfuscated = [l for l in gout.splitlines() if l.strip()]
    # preg_replace /e séparément (modificateur dangereux)
    preg_pat = shlex.quote(r"preg_replace\s*\(.*/e")
    rc, pout, _ = ssh.run(
        f"grep -rlE {preg_pat} {qpath}/wp-content --include='*.php' 2>/dev/null | head -50")
    preg_e = [l for l in pout.splitlines() if l.strip()]

    waves: dict[str, int] = {}
    for item in flagged_files + generated_themes:
        if "date" in item:
            waves[item["date"]] = waves.get(item["date"], 0) + 1

    return {
        "site": site.name,
        "flagged_files": flagged_files,
        "generated_themes": generated_themes,
        "obfuscated_php": obfuscated,
        "preg_replace_e": preg_e,
        "waves_by_date": waves,
    }


def module_persistence(ssh: SSH, site: Site, deep: bool = False) -> dict:
    qpath = shlex.quote(site.path)
    result: dict[str, Any] = {"site": site.name}

    # mu-plugins
    rc, out, _ = ssh.run(f"ls -1 {qpath}/wp-content/mu-plugins 2>/dev/null")
    result["mu_plugins"] = [l for l in out.splitlines() if l.strip()]

    # tâches cron
    cron = _json_wp(ssh, site, "cron event list --fields=hook,next_run,schedule") or []
    result["cron_events"] = cron

    # comptes admin + trous d'ID
    users = _json_wp(ssh, site, "user list --fields=ID,user_login,roles") or []
    ids = sorted(int(u["ID"]) for u in users if str(u.get("ID", "")).isdigit())
    gaps = []
    if ids:
        full = set(range(min(ids), max(ids) + 1))
        gaps = sorted(full - set(ids))
    result["users_count"] = len(users)
    result["admins"] = [u for u in users if "administrator" in (u.get("roles") or "")]
    result["id_gaps"] = gaps

    # Application Passwords (nécessite WP 5.6+ ; best-effort)
    rc, apout, _ = ssh.run(
        f"{shlex.quote(ssh.cfg.wp_bin)} --path={qpath} user application-password list "
        f"$( {shlex.quote(ssh.cfg.wp_bin)} --path={qpath} user list --field=ID | tr '\\n' ' ') "
        f"--format=json 2>/dev/null")
    try:
        result["application_passwords"] = json.loads(apout) if apout.strip() else []
    except json.JSONDecodeError:
        result["application_passwords"] = []

    # wp_options autoloaded volumineux (payloads parfois en base)
    big = _json_wp(ssh, site,
                   "option list --autoload=on --fields=option_name --format=json") or []
    result["autoloaded_options_count"] = len(big) if isinstance(big, list) else 0

    # .htaccess racine + uploads
    for label, rel in (("root", ""), ("uploads", "/wp-content/uploads")):
        rc, hout, _ = ssh.run(f"cat {qpath}{rel}/.htaccess 2>/dev/null")
        suspicious = [l for l in hout.splitlines()
                      if re.search(r"(RewriteRule|RewriteCond).*(https?://|base64|eval)", l, re.I)
                      or "AddType" in l and "php" in l.lower()]
        result[f"htaccess_{label}_suspicious"] = suspicious

    # functions.php du thème actif
    rc, active, _ = ssh.wp(site, "theme list --status=active --field=name")
    active = active.strip().splitlines()[0] if active.strip() else ""
    result["active_theme"] = active
    if active:
        fpath = f"{site.path}/wp-content/themes/{active}/functions.php"
        rc, fout, _ = ssh.run(f"grep -nE {shlex.quote('|'.join(re.escape(s) for s in ['eval(','base64_decode','gzinflate','str_rot13','assert(','create_function']))} {shlex.quote(fpath)} 2>/dev/null")
        result["functions_php_markers"] = [l for l in fout.splitlines() if l.strip()]

    # score de suspicion rapide
    flags = (len(result["mu_plugins"]) > 0) + bool(gaps) + \
            bool(result.get("functions_php_markers")) + \
            any(result.get(f"htaccess_{l}_suspicious") for l in ("root", "uploads")) + \
            (len(result.get("application_passwords") or []) > 0)
    result["persistence_flags"] = int(flags)
    return result


# --------------------------------------------------------------------------- #
# Rapport (module 6) : checklist Annexe A par site                              #
# --------------------------------------------------------------------------- #

def build_report(ssh: SSH, site: Site) -> dict:
    inv = module_inventory(ssh, site)
    chk = module_checksums(ssh, site)
    sig = module_signatures(ssh, site)
    per = module_persistence(ssh, site)

    checks = {
        "core_checksums": chk["core_ok"],
        "plugin_checksums": chk["plugins_ok"],
        "premium_diff": None,  # manuel
        "no_unknown_php": len(sig["flagged_files"]) == 0,
        "no_generated_theme": len(sig["generated_themes"]) == 0,
        "mu_plugins_clean": len(per["mu_plugins"]) == 0,
        "no_rogue_admin": len(per["id_gaps"]) == 0,
        "no_app_passwords": len(per.get("application_passwords") or []) == 0,
        "cron_clean": None,  # à relire à la main
        "functions_clean": len(per.get("functions_php_markers") or []) == 0,
        "htaccess_clean": not any(per.get(f"htaccess_{l}_suspicious")
                                  for l in ("root", "uploads")),
        "secrets_rotated": None,   # manuel
        "wordfence_clean": None,   # manuel
        "infomaniak_clean": None,  # manuel
        "no_spam_indexed": None,   # manuel
    }
    auto = [v for v in checks.values() if v is not None]
    green = all(auto) if auto else False
    return {
        "site": site.name, "category": site.category,
        "generated": now_utc().isoformat(),
        "inventory": inv, "checksums": chk, "signatures": sig, "persistence": per,
        "annexe_a": checks,
        "annexe_a_auto_pass": sum(1 for v in auto if v),
        "annexe_a_auto_total": len(auto),
        "annexe_a_all_green_auto": green,
    }


def report_to_markdown(rep: dict) -> str:
    site = rep["site"]
    lines = [f"# Rapport — {site} (cat. {rep['category']})",
             f"_Généré : {rep['generated']}_", ""]
    inv = rep["inventory"]
    lines += [f"- WP {inv['wp_version']} · {inv['php_version']}",
              f"- {inv['plugins_count']} extensions · {inv['themes_count']} thèmes "
              f"· {inv['admins_count']} admin(s)", ""]
    sig = rep["signatures"]
    if sig["waves_by_date"]:
        waves = ", ".join(f"{d} ({n})" for d, n in sorted(sig["waves_by_date"].items()))
        lines += [f"**Vagues datées (timestamps Unix) :** {waves}", ""]
    lines.append("## Annexe A — site déclaré sain")
    for key, label in ANNEXE_A:
        v = rep["annexe_a"].get(key)
        mark = {True: "[x]", False: "[ ]", None: "[~]"}[v]
        suffix = " _(vérif. manuelle)_" if v is None else ""
        lines.append(f"- {mark} {label}{suffix}")
    lines += ["", f"**Auto : {rep['annexe_a_auto_pass']}/{rep['annexe_a_auto_total']} "
                  f"points automatiques verts.**"]
    if not rep["annexe_a_all_green_auto"]:
        lines.append("> ⚠️ Ne pas remettre en ligne : des points automatiques sont rouges.")
    # détails saillants
    ff = sig["flagged_files"]
    if ff:
        lines += ["", "### Fichiers signalés"]
        for e in ff[:50]:
            d = f" → {e['date']}" if "date" in e else ""
            lines.append(f"- `{e['path']}` ({e['reason']}){d}")
    per = rep["persistence"]
    if per["mu_plugins"]:
        lines += ["", f"### mu-plugins ({len(per['mu_plugins'])})",
                  *[f"- `{m}`" for m in per["mu_plugins"]]]
    if per["id_gaps"]:
        lines += ["", f"### Trous d'ID utilisateur : {per['id_gaps']}"]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Nettoyage (module 7) — GARDÉ                                                   #
# --------------------------------------------------------------------------- #

def module_clean(ssh: SSH, site: Site, store: SnapshotStore, log: IncidentLog,
                 execute: bool) -> None:
    # GARDE-FOU BLOQUANT : un snapshot vérifié doit exister pour ce site.
    verified = store.latest_verified_backup(site.name)
    if verified is None:
        human(f"  🔴 {site.name} : AUCUN snapshot vérifié. `clean` refuse de s'exécuter.\n"
              f"     Lance d'abord : mb_remediation.py backup --site={site.name} --status=INFECTE --execute",
              "err")
        log.write("clean_refused", site=site.name, reason="no_verified_backup")
        return
    human(f"  filet OK (snapshot vérifié : {verified.name})", "step")

    # cibles connues (Annexe B) : on liste, on ne supprime qu'avec --execute
    sig = module_signatures(ssh, site)
    targets = [e["path"] for e in sig["flagged_files"]] + \
              [t["path"] for t in sig["generated_themes"]]
    # artefacts connus supplémentaires
    for rel in ("wp-content/Liar-Console.php",
                "wp-content/plugins/all-in-one-wp-migration",
                "wp-content/ai1wm-backups",
                "wp-content/uploads/backup"):
        rc, out, _ = ssh.run(f"test -e {shlex.quote(site.path + '/' + rel)} && echo yes")
        if out.strip() == "yes":
            targets.append(site.path + "/" + rel)

    targets = sorted(set(targets))
    if not targets:
        human(f"  ✓ {site.name} : aucun artefact connu à supprimer.", "ok")
        return

    human(f"  {len(targets)} cible(s) sur {site.name} :", "warn")
    for t in targets:
        human(f"    - {t}")

    if not execute:
        human(f"  [dry-run] rien supprimé. Ajoute --execute pour agir.", "warn")
        log.write("clean_dryrun", site=site.name, targets=targets)
        return

    for t in targets:
        # sécurité : ne jamais toucher hors de site.path
        if not posixpath.normpath(t).startswith(posixpath.normpath(site.path) + "/"):
            human(f"    ⚠ ignoré (hors racine du site) : {t}", "err")
            continue
        rc, out, err = ssh.run(f"rm -rf {shlex.quote(t)}")
        ok = rc == 0
        human(f"    {'✓' if ok else '✗'} rm {t}", "ok" if ok else "err")
        log.write("clean_delete", site=site.name, target=t, ok=ok, err=err.strip())


# --------------------------------------------------------------------------- #
# Rotation des secrets (Phase 2.3) — GARDÉ                                       #
# --------------------------------------------------------------------------- #

def _strong_password(length: int = 24) -> str:
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits + "!@#%^*-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def module_rotate(ssh: SSH, site: Site, store: SnapshotStore, log: IncidentLog,
                  out_dir: Path, execute: bool, db_password: Optional[str]) -> None:
    """Régénère les salts, réinitialise les mots de passe admin, et (optionnel)
    reporte un nouveau mot de passe DB dans wp-config. Les nouveaux mots de passe
    sont écrits UNIQUEMENT dans un fichier LOCAL (jamais dans le log JSONL)."""
    # GARDE-FOU : snapshot vérifié requis (on modifie wp-config + table users).
    verified = store.latest_verified_backup(site.name)
    if verified is None:
        human(f"  🔴 {site.name} : aucun snapshot vérifié. `rotate` refuse.\n"
              f"     Lance d'abord : backup --site={site.name} --status=INFECTE --execute", "err")
        log.write("rotate_refused", site=site.name, reason="no_verified_backup")
        return

    admins = _json_wp(ssh, site, "user list --role=administrator --fields=ID,user_login") or []
    human(f"  {len(admins)} admin(s), salts, "
          f"{'+ mot de passe DB' if db_password else 'DB inchangée'}", "step")

    if not execute:
        human(f"  [dry-run] régénérerait les 8 salts (wp config shuffle-salts)", "warn")
        for a in admins:
            human(f"  [dry-run] réinitialiserait le mot de passe de « {a['user_login']} »", "warn")
        if db_password:
            human(f"  [dry-run] reporterait DB_PASSWORD dans wp-config.php", "warn")
        log.write("rotate_dryrun", site=site.name, admins=len(admins))
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    cred_file = out_dir / f"{site.name}.new-credentials.txt"
    lines = [f"# {site.name} — nouveaux secrets générés le {now_utc().isoformat()}",
             f"# À stocker dans ton gestionnaire de mots de passe, puis SUPPRIMER ce fichier.\n"]

    # 1) salts (déconnecte toutes les sessions)
    rc, out, err = ssh.wp(site, "config shuffle-salts", check=False)
    ok = rc == 0
    human(f"  {'✓' if ok else '✗'} salts régénérés", "ok" if ok else "err")
    log.write("rotate_salts", site=site.name, ok=ok, err=err.strip())

    # 2) mots de passe admin (nouveau mdp aléatoire, écrit en local seulement)
    for a in admins:
        pw = _strong_password()
        rc, out, err = ssh.wp(site, f"user update {shlex.quote(str(a['ID']))} "
                                    f"--user_pass={shlex.quote(pw)}", check=False)
        ok = rc == 0
        human(f"  {'✓' if ok else '✗'} mot de passe réinitialisé : {a['user_login']}",
              "ok" if ok else "err")
        # le mot de passe n'apparaît QUE dans le fichier local, jamais dans le log
        lines.append(f"admin {a['user_login']} (ID {a['ID']}) : {pw}" if ok
                     else f"admin {a['user_login']} (ID {a['ID']}) : ÉCHEC")
        log.write("rotate_admin", site=site.name, user=a["user_login"], ok=ok)

    # 3) mot de passe DB (le changement MySQL se fait dans le Manager Infomaniak ;
    #    ici on ne fait que reporter la nouvelle valeur dans wp-config.php)
    if db_password:
        rc, out, err = ssh.wp(site, f"config set DB_PASSWORD {shlex.quote(db_password)}",
                              check=False)
        ok = rc == 0
        human(f"  {'✓' if ok else '✗'} DB_PASSWORD reporté dans wp-config.php", "ok" if ok else "err")
        lines.append(f"DB_PASSWORD : (reporté dans wp-config ; change-le AUSSI côté MySQL/Manager)")
        log.write("rotate_db", site=site.name, ok=ok)
    else:
        human("  → mot de passe DB non touché — change-le dans le Manager Infomaniak "
              "puis relance avec --db-password=<nouveau>", "warn")

    cred_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(cred_file, 0o600)
    except OSError:
        pass
    human(f"  ✓ nouveaux secrets écrits (local, chmod 600) : {cred_file}", "ok")
    human("  ⚠️ range-les dans ton gestionnaire puis SUPPRIME ce fichier.", "warn")


# --------------------------------------------------------------------------- #
# Restore (module 0)                                                             #
# --------------------------------------------------------------------------- #

def do_restore(args, cfg: Config, store: SnapshotStore, log: IncidentLog) -> None:
    snap = Path(args.snapshot).expanduser()
    if not snap.is_absolute():
        snap = cfg.backup_dir / args.snapshot
    if not snap.exists():
        sys.exit(f"Snapshot introuvable : {snap}")
    meta = json.loads((snap / "meta.json").read_text(encoding="utf-8"))
    status = meta.get("status", "?")

    if args.full:
        if status == STATUS_INFECTED:
            sys.exit("🔴 restore --full REFUSÉ : snapshot INFECTÉ (réinjecterait le malware).")
        if status != STATUS_VERIFIED and not args.i_understand:
            sys.exit(f"Snapshot {status} (non VÉRIFIÉ). Restauration complète bloquée.\n"
                     f"Confirme explicitement avec --i-understand si tu sais ce que tu fais.")
        human("restore --full : non implémenté en poussée automatique (garde-fou volontaire).", "warn")
        human("Le snapshot contient files.tar.gz + db.sql ; restaure manuellement, "
              "en connaissance de cause, hors de ce script.", "warn")
        log.write("restore_full_requested", snapshot=snap.name, status=status)
        return

    if args.file:
        human(f"Extraction ciblée de « {args.file} » depuis {snap.name}", "step")
        import tarfile
        with tarfile.open(snap / "files.tar.gz", "r:gz") as tf:
            member = None
            for m in tf:
                if m.name.lstrip("./") == args.file.lstrip("./"):
                    member = m
                    break
            if member is None:
                sys.exit(f"Fichier « {args.file} » absent du snapshot.")
            out = Path(args.restore_out or ".").expanduser() / posixpath.basename(args.file)
            with tf.extractfile(member) as src, out.open("wb") as dst:  # type: ignore
                dst.write(src.read())
        human(f"✓ extrait localement → {out} (remonte-le toi-même via SFTP)", "ok")
        log.write("restore_file", snapshot=snap.name, file=args.file, out=str(out))
        return

    sys.exit("Précise --file=<chemin>, --db-table=<table> ou --full.")


# --------------------------------------------------------------------------- #
# Diff (module 0)                                                               #
# --------------------------------------------------------------------------- #

def do_diff(ssh: SSH, site: Site, snap: Path) -> None:
    manifest_p = snap / "manifest.json"
    if not manifest_p.exists():
        sys.exit(f"Manifeste absent : {manifest_p}")
    old = json.loads(manifest_p.read_text(encoding="utf-8"))
    qpath = shlex.quote(site.path)
    rc, out, _ = ssh.run(f"cd {qpath} && find . -type f -print0 | xargs -0 sha256sum 2>/dev/null")
    new = {}
    for line in out.splitlines():
        if "  " in line:
            h, f = line.split("  ", 1)
            new[f] = h
    old_set, new_set = set(old), set(new)
    added = sorted(new_set - old_set)
    removed = sorted(old_set - new_set)
    modified = sorted(f for f in (old_set & new_set) if old[f] != new[f])
    human(f"Diff {site.name} vs {snap.name}", "step")
    human(f"  + {len(added)} ajoutés   - {len(removed)} supprimés   ~ {len(modified)} modifiés")
    for f in added[:100]:
        human(f"    + {f}", "warn")
    for f in modified[:100]:
        human(f"    ~ {f}", "warn")
    if added or modified:
        human("  ⚠️ Des fichiers ont APPARU/CHANGÉ depuis le snapshot — vérifie qu'il "
              "ne s'agit pas d'une réinfection (cron/mu-plugin/clé SSH oubliée).", "err")


# --------------------------------------------------------------------------- #
# Orchestration CLI                                                             #
# --------------------------------------------------------------------------- #

READ_ONLY = {"inventory", "checksums", "signatures", "persistence", "report"}


def run_readonly(cmd: str, ssh: SSH, sites: list[Site], log: IncidentLog,
                 out_dir: Path, deep: bool = False) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    aggregate = []
    for site in sites:
        human(f"[{cmd}] {site.name}", "step")
        try:
            if cmd == "inventory":
                data = module_inventory(ssh, site)
            elif cmd == "checksums":
                data = module_checksums(ssh, site)
            elif cmd == "signatures":
                data = module_signatures(ssh, site)
                if data["waves_by_date"]:
                    for d, n in sorted(data["waves_by_date"].items()):
                        human(f"    vague {d} : {n} artefact(s)", "warn")
            elif cmd == "persistence":
                data = module_persistence(ssh, site, deep=deep)
                if data["persistence_flags"]:
                    human(f"    ⚠ {data['persistence_flags']} signal(aux) de persistance", "warn")
            elif cmd == "report":
                data = build_report(ssh, site)
                (out_dir / f"{site.name}.report.md").write_text(
                    report_to_markdown(data), encoding="utf-8")
                tag = "VERT" if data["annexe_a_all_green_auto"] else "ROUGE"
                human(f"    Annexe A auto : {data['annexe_a_auto_pass']}/"
                      f"{data['annexe_a_auto_total']} ({tag})",
                      "ok" if data["annexe_a_all_green_auto"] else "warn")
            else:  # pragma: no cover
                continue
            (out_dir / f"{site.name}.{cmd}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            aggregate.append(data)
            log.write(cmd, site=site.name)
        except Exception as e:  # noqa: BLE001
            human(f"    ✗ erreur : {e}", "err")
            log.write(f"{cmd}_error", site=site.name, error=str(e))
    (out_dir / f"_{cmd}.all.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2), encoding="utf-8")
    human(f"→ résultats : {out_dir}", "ok")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mb_remediation.py",
        description="Outillage de remédiation WordPress multi-sites (SSH + WP-CLI). "
                    "Tourne chez toi ; ne dépose rien sur le serveur.")
    p.add_argument("--config", default="sites.yaml", help="Fichier de config (défaut: sites.yaml)")
    p.add_argument("--out", default="mb-out", help="Dossier de sortie des rapports")
    sub = p.add_subparsers(dest="command", required=True)

    def add_site_selectors(sp, destructive=False):
        sp.add_argument("--site", action="append", default=[],
                        help="Nom de site (répétable). " +
                             ("OBLIGATOIRE en destructif." if destructive else "Ou --all."))
        if not destructive:
            sp.add_argument("--all", action="store_true", help="Tous les sites")

    for name in ("inventory", "checksums", "signatures", "persistence", "report"):
        sp = sub.add_parser(name, help=f"Module lecture seule : {name}")
        add_site_selectors(sp)
        if name == "persistence":
            sp.add_argument("--deep", action="store_true", help="Analyse approfondie")

    sp = sub.add_parser("backup", help="Module 0 : snapshot fichiers + BDD + manifeste")
    add_site_selectors(sp)
    sp.add_argument("--status", choices=VALID_STATUSES, default=STATUS_INFECTED,
                    help="Type de snapshot (défaut: INFECTE)")
    sp.add_argument("--execute", action="store_true", help="Écrit réellement (sinon dry-run)")

    sp = sub.add_parser("verify", help="Vérifie l'intégrité d'un snapshot")
    sp.add_argument("snapshot", help="Nom (dans backup_dir) ou chemin du snapshot")

    sp = sub.add_parser("diff", help="Compare l'état d'un site à un snapshot")
    sp.add_argument("--site", required=True, help="Site à comparer")
    sp.add_argument("--snapshot", required=True, help="Snapshot de référence")

    sp = sub.add_parser("restore", help="Restauration chirurgicale (défaut) ou --full (gardée)")
    sp.add_argument("--snapshot", required=True)
    sp.add_argument("--file", help="Extraire un fichier précis (mode par défaut)")
    sp.add_argument("--db-table", dest="db_table", help="Restaurer une table (best-effort)")
    sp.add_argument("--full", action="store_true", help="Restauration complète (bloquée si INFECTE)")
    sp.add_argument("--dest", dest="restore_out", help="Où écrire le fichier extrait (défaut: .)")
    sp.add_argument("--i-understand", action="store_true",
                    help="Confirme une restauration non-VÉRIFIÉE")

    sp = sub.add_parser("clean", help="Module 7 : suppression (dry-run par défaut, gardé par backup)")
    add_site_selectors(sp, destructive=True)
    sp.add_argument("--execute", action="store_true", help="Supprime réellement (sinon dry-run)")

    sp = sub.add_parser("rotate", help="Phase 2.3 : salts + mots de passe admin (+ DB). Gardé par backup.")
    sp.add_argument("--site", action="append", default=[], help="Nom de site (répétable)")
    sp.add_argument("--all", action="store_true", help="Tous les sites")
    sp.add_argument("--db-password", dest="db_password",
                    help="Nouveau DB_PASSWORD à reporter dans wp-config (après changement Manager)")
    sp.add_argument("--execute", action="store_true", help="Agit réellement (sinon dry-run)")

    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = Config.load(Path(args.config).expanduser())
    log = IncidentLog(cfg.backup_dir / "mb-remediation.log")
    out_dir = Path(getattr(args, "out", None) or "mb-out").expanduser()
    store = SnapshotStore(cfg, log)

    # commandes hors-ligne (pas de SSH)
    if args.command == "verify":
        snap = Path(args.snapshot).expanduser()
        if not snap.is_absolute():
            snap = cfg.backup_dir / args.snapshot
        ok, problems = store.verify(snap)
        human(f"Snapshot {snap.name} : {'VÉRIFIÉ ✓' if ok else 'ÉCHEC ✗'}",
              "ok" if ok else "err")
        for pb in problems:
            human(f"  - {pb}", "err")
        return 0 if ok else 2

    if args.command == "restore":
        do_restore(args, cfg, store, log)
        return 0

    # --- validation des arguments AVANT toute connexion SSH ---
    if args.command == "clean":
        if getattr(args, "all", False):
            sys.exit("🔴 `clean --all` interdit. Un site à la fois (--site=<nom>).")
        if not args.site:
            sys.exit("🔴 `clean` exige --site=<nom> (jamais les 25 d'un coup).")
    if args.command in READ_ONLY or args.command in ("backup", "rotate"):
        if not cfg.select(args.site, getattr(args, "all", False)):
            sys.exit("Précise --site=<nom> (répétable) ou --all.")

    # commandes nécessitant SSH
    with SSH(cfg) as ssh:
        if args.command in READ_ONLY:
            sites = cfg.select(args.site, getattr(args, "all", False))
            if not sites:
                sys.exit("Précise --site=<nom> (répétable) ou --all.")
            run_readonly(args.command, ssh, sites, log, out_dir,
                         deep=getattr(args, "deep", False))
            return 0

        if args.command == "backup":
            sites = cfg.select(args.site, getattr(args, "all", False))
            if not sites:
                sys.exit("Précise --site=<nom> ou --all.")
            for site in sites:
                human(f"[backup {args.status}] {site.name}", "step")
                store.backup(ssh, site, args.status,
                             command=" ".join(sys.argv), dry_run=not args.execute)
            return 0

        if args.command == "diff":
            site = cfg.select([args.site], False)[0]
            snap = Path(args.snapshot).expanduser()
            if not snap.is_absolute():
                snap = cfg.backup_dir / args.snapshot
            do_diff(ssh, site, snap)
            return 0

        if args.command == "clean":
            if getattr(args, "all", False):
                sys.exit("🔴 `clean --all` interdit. Un site à la fois (--site=<nom>).")
            if not args.site:
                sys.exit("🔴 `clean` exige --site=<nom> (jamais les 25 d'un coup).")
            sites = cfg.select(args.site, False)
            for site in sites:
                human(f"[clean] {site.name} ({'EXECUTE' if args.execute else 'dry-run'})", "step")
                module_clean(ssh, site, store, log, execute=args.execute)
            return 0

        if args.command == "rotate":
            sites = cfg.select(args.site, getattr(args, "all", False))
            for site in sites:
                human(f"[rotate] {site.name} ({'EXECUTE' if args.execute else 'dry-run'})", "step")
                module_rotate(ssh, site, store, log, out_dir,
                              execute=args.execute, db_password=args.db_password)
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
