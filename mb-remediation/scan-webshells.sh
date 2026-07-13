#!/usr/bin/env bash
# ============================================================================
# scan-webshells.sh — chasse au webshell / persistance, 100 % LECTURE SEULE
# ----------------------------------------------------------------------------
# Ne modifie, ne supprime, ne déplace RIEN. Ne fait qu'inspecter et afficher.
# Couvre les tâches 1 (webshells) et 2 (cron) du brief d'incident MB1.
#
# USAGE (depuis TA machine, capture le rapport en local) :
#   ssh d56bh5_nico@d56bh5.ftp.infomaniak.com 'bash -s' < scan-webshells.sh \
#       > scan_$(date +%F).txt 2>&1
#
# ou directement sur le serveur (le résultat s'affiche à l'écran) :
#   bash scan-webshells.sh [CHEMIN]        # CHEMIN par défaut = $HOME
#
# Rien n'est écrit sur le serveur : tout part sur la sortie standard.
# ============================================================================
set -uo pipefail

ROOT="${1:-$HOME}"
RECENT_DAYS=60          # PHP modifiés dans les N derniers jours
HOT_DAYS=14             # fenêtre "chaude" (post-quarantaine)

echo "=========================================================="
echo " scan-webshells.sh — LECTURE SEULE"
echo " racine : $ROOT"
echo " date   : $(date -u '+%Y-%m-%d %H:%M:%SZ')  (UTC)"
echo " hôte   : $(hostname 2>/dev/null || echo '?')"
echo "=========================================================="

# --- 0. Décodage des timestamps Unix dans les noms (datation des vagues) -----
decode_ts() {
  # lit des chemins sur stdin, annote ceux qui contiennent un timestamp Unix
  while IFS= read -r f; do
    base="$(basename "$f")"
    ts="$(printf '%s' "$base" | grep -oE '(^|[^0-9])(1[0-9]{9})([^0-9]|$)' \
          | grep -oE '1[0-9]{9}' | head -1)"
    if [ -n "${ts:-}" ]; then
      d="$(date -u -d "@$ts" '+%Y-%m-%d' 2>/dev/null || echo '?')"
      echo "  $f   ⟵ timestamp $ts = $d"
    else
      echo "  $f"
    fi
  done
}

# --- 1. Fichiers PHP récemment modifiés --------------------------------------
echo
echo "### 1a. PHP modifiés dans les $HOT_DAYS derniers jours (fenêtre chaude)"
find "$ROOT" -type f -name '*.php' -mtime -"$HOT_DAYS" -printf '%TY-%Tm-%Td %TH:%TM  %p\n' \
  2>/dev/null | sort | head -300
echo
echo "### 1b. PHP modifiés dans les $RECENT_DAYS derniers jours (comptage par jour)"
find "$ROOT" -type f -name '*.php' -mtime -"$RECENT_DAYS" -printf '%TY-%Tm-%Td\n' \
  2>/dev/null | sort | uniq -c | sort -rn | head -40

# --- 2. Patterns de webshell dans le code PHP --------------------------------
echo
echo "### 2. Fichiers PHP contenant des marqueurs de webshell/obfuscation"
echo "     (eval, base64_decode, gzinflate, str_rot13, assert, system,"
echo "      shell_exec, passthru, \$_GET/POST/REQUEST exécutés…)"
grep -rIlE \
  'eval\(|base64_decode\(|gzinflate\(|str_rot13\(|assert\(|system\(|shell_exec\(|passthru\(|popen\(|proc_open\(|\$_(GET|POST|REQUEST|COOKIE)\[' \
  --include='*.php' "$ROOT" 2>/dev/null | head -300 | decode_ts

echo
echo "### 2b. preg_replace avec modificateur /e (exécution de code — rare et dangereux)"
grep -rIlE 'preg_replace[[:space:]]*\([^)]*/e' --include='*.php' "$ROOT" 2>/dev/null | head -100

echo
echo "### 2c. Marqueurs de webshells connus (FilesMan, WSO, c99, Liar-Console…)"
grep -rIlE 'FilesMan|WSOshell|c99sh|r57shell|Liar|MiniShell|b374k|phpspy' \
  --include='*.php' "$ROOT" 2>/dev/null | head -100

# --- 3. PHP là où il ne devrait pas y en avoir ------------------------------
echo
echo "### 3a. Fichiers PHP/exécutables DANS les uploads (jamais légitime)"
find "$ROOT" -type f \( -name '*.php' -o -name '*.phtml' -o -name '*.php5' \
  -o -name '*.php7' -o -name '*.pht' -o -name '*.suspected' \) \
  -path '*/uploads/*' 2>/dev/null | head -200 | decode_ts

echo
echo "### 3b. Fichiers à nom de timestamp Unix (signature des deux vagues)"
find "$ROOT" -type f -name '*_1[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].php' \
  2>/dev/null | head -200 | decode_ts

echo
echo "### 3c. Dossiers de thème à nom généré (<mot>-<timestamp>)"
find "$ROOT" -type d -path '*/themes/*' -maxdepth 12 \
  -regextype posix-extended -regex '.*[-_]1[0-9]{9}$' 2>/dev/null | head -100 | decode_ts

echo
echo "### 3d. Artefacts connus du runbook"
for pat in 'Liar-Console.php' 'all-in-one-wp-migration' 'ai1wm-backups' '_quarantaine_*'; do
  find "$ROOT" -maxdepth 12 -name "$pat" 2>/dev/null | head -50
done

# --- 4. mu-plugins (s'exécutent tout seuls, invisibles dans wp-admin) --------
echo
echo "### 4. mu-plugins présents (à relire un par un — cachette n°1)"
find "$ROOT" -type f -path '*/mu-plugins/*.php' 2>/dev/null | head -100 | decode_ts

# --- 5. Tâches planifiées (persistance classique) ----------------------------
echo
echo "### 5. Tâches cron système de l'utilisateur"
crontab -l 2>/dev/null || echo "  (aucune crontab, ou commande indisponible sur ce mutualisé)"
echo
echo "     (Les crons WordPress sont en base ; vérifie-les par site avec"
echo "      'wp cron event list' ou le module persistence de mb-remediation.)"

# --- 6. .htaccess suspects (redirections / cloaking) -------------------------
echo
echo "### 6. .htaccess contenant des redirections/exécutions suspectes"
grep -rIlE 'RewriteRule.*(https?://|base64|eval)|AddType.*php|php_value auto_(prepend|append)_file' \
  --include='.htaccess' "$ROOT" 2>/dev/null | head -100

echo
echo "=========================================================="
echo " Fin du scan. RIEN n'a été modifié."
echo " Analyse les sorties ci-dessus ; ne supprime rien sans double-vérif"
echo " et sans sauvegarde préalable (module backup de mb-remediation)."
echo "=========================================================="
