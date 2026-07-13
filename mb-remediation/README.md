# mb-remediation

Outillage d'incident-response WordPress multi-sites pour la compromission du
compte Infomaniak MB1. **Tourne sur ta machine**, pilote les 25 sites en
**SSH + WP-CLI**, et **ne dépose aucun fichier sur le serveur** (un script PHP
posé dans l'arbo serait un webshell — exactement ce qu'on nettoie).

> ⚠️ Cet outil **n'exécute pas** la Phase 0 (rotation de tes accès), la Phase 3
> (reconstruction) ni la Phase 5 (obligations légales). Il **accélère** le
> diagnostic et le nettoyage ; il ne les remplace pas. Voir le runbook.

## Installation (sur ta machine, pas sur le serveur)

```bash
cd mb-remediation
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp sites.example.yaml sites.yaml   # puis édite sites.yaml
```

Dans `sites.yaml` : hôte SSH, **le nouveau compte** (après rotation Phase 0),
le chemin de ta **clé SSH** (aucun mot de passe en dur), et la racine WordPress
(`path`) de chaque site. `sites.yaml` est git-ignoré : ne le committe jamais.

## Le plus urgent, sans rien installer : le scan lecture seule

Pour la **chasse au webshell (tâche 1)** et le **cron (tâche 2)**, tu n'as même
pas besoin de Python. Lance le script depuis ta machine, capture le rapport en
local :

```bash
ssh d56bh5_nico@d56bh5.ftp.infomaniak.com 'bash -s' < scan-webshells.sh \
    > scan_$(date +%F).txt 2>&1
```

100 % lecture seule (aucune modification), il liste : PHP récemment modifiés,
marqueurs de webshell, PHP dans `uploads`, fichiers/dossiers à nom de timestamp
(datés automatiquement), mu-plugins, crontab, `.htaccess` suspects.

Les mêmes hunts sont intégrés à l'outil (ci-dessous) via `scan`, avec sortie
JSON + Markdown.

## Ordre d'utilisation (imposé par le runbook)

**0. Découverte + scan (lecture seule, home entier — commence par là) :**

```bash
python3 mb_remediation.py discover   # trouve tous les wp-config.php → liste YAML
python3 mb_remediation.py scan       # webshells + cron sur tout le home → mb-out/_scan.md
```

`discover` te génère le bloc `sites:` à coller dans `sites.yaml` (utile : ton
environnement compte ~20 sites aux chemins inconnus). `scan` produit un rapport
daté (`mb-out/_scan.md` + `_scan.json`).

**1. Le filet — snapshot avant de toucher à quoi que ce soit :**

```bash
# dry-run par défaut : montre ce qui serait fait
python3 mb_remediation.py backup --site=poeles-cheminees.com --status=INFECTE
# puis pour de vrai
python3 mb_remediation.py backup --site=poeles-cheminees.com --status=INFECTE --execute
python3 mb_remediation.py verify 2026-07-13_14-30-00_poeles-cheminees.com_INFECTE
```

**2. Cartographie en lecture seule (aucun risque) :**

```bash
python3 mb_remediation.py inventory   --all
python3 mb_remediation.py checksums   --all
python3 mb_remediation.py signatures  --all      # date les vagues via les timestamps Unix
python3 mb_remediation.py persistence --all --deep
python3 mb_remediation.py report      --all      # → mb-out/<site>.report.md (Annexe A)
```

**3. Nettoyage — en dernier, un site à la fois, et seulement Phase 0 terminée :**

```bash
python3 mb_remediation.py clean --site=poeles-cheminees.com            # dry-run
python3 mb_remediation.py clean --site=poeles-cheminees.com --execute  # agit
```

`clean` **refuse de démarrer** s'il n'existe pas de snapshot vérifié pour le site.

**3bis. Rotation des secrets (Phase 2.3) — après nettoyage, gardé par backup :**

```bash
python3 mb_remediation.py rotate --site=poeles-cheminees.com            # dry-run
python3 mb_remediation.py rotate --site=poeles-cheminees.com --execute  # salts + mdp admin
# après avoir changé le mot de passe MySQL dans le Manager Infomaniak :
python3 mb_remediation.py rotate --site=poeles-cheminees.com --execute --db-password='NOUVEAU'
```

`rotate` régénère les 8 salts (déconnecte toutes les sessions), réinitialise les
mots de passe admin (nouveaux mots de passe écrits **uniquement** dans
`mb-out/<site>.new-credentials.txt`, chmod 600, **jamais dans le log**), et
reporte `DB_PASSWORD` dans wp-config si tu passes `--db-password`. Le changement
MySQL lui-même se fait dans le Manager Infomaniak.

**4. Vérifier que rien ne repousse (après 48 h) :**

```bash
python3 mb_remediation.py diff --site=poeles-cheminees.com \
        --snapshot=2026-07-13_14-30-00_poeles-cheminees.com_INFECTE
```

Si des fichiers ont **apparu** → l'accès n'est pas fermé (cron / mu-plugin / clé
SSH oubliée) → retour Phase 0.

## Modules

| Module | Rôle | Destructif ? |
|---|---|---|
| `discover` | Trouve toutes les installations WordPress sous `home` → bloc `sites:` prêt à coller. | non |
| `scan` | Chasse au webshell/cron sur **tout le home** (marqueurs, PHP dans uploads, timestamps datés, mu-plugins, crontab, .htaccess). | non |
| `backup` | Snapshot fichiers (tar.gz) + BDD (`wp db export`) + manifeste SHA-256 + méta. Typé **INFECTE / ENCOURS / VERIFIE**. | non (écrit en local) |
| `verify` | Contrôle d'intégrité d'un snapshot (archive ouvrable, dump non tronqué, manifeste cohérent). | non |
| `diff` | Compare l'état actuel d'un site à un snapshot → ce qui a changé. | non |
| `restore` | `--file` (chirurgical, défaut) · `--full` **bloqué si INFECTE**. | non (extrait en local) |
| `inventory` | Versions WP/PHP, extensions, thèmes, comptes admin. | non |
| `checksums` | `wp core/plugin verify-checksums`. | non |
| `signatures` | Patterns Annexe B + **décodage des timestamps Unix → dates** (datation des vagues). | non |
| `persistence` | mu-plugins, cron, comptes + **trous d'ID**, Application Passwords, options autoloaded, `.htaccess`, `functions.php`. | non |
| `report` | Checklist **Annexe A** par site (Markdown + JSON). | non |
| `clean` | Suppression des artefacts connus. **`--dry-run` par défaut**, `--execute` explicite, `--site` obligatoire, **refuse sans snapshot vérifié**. | **oui** |
| `rotate` | Phase 2.3 : régénère les salts, réinitialise les mots de passe admin (écrits en local, jamais loggés), reporte `DB_PASSWORD`. `--dry-run` par défaut, **refuse sans snapshot vérifié**. | **oui** |

## Garde-fous (non contournables)

- `clean` refuse de s'exécuter sans snapshot **vérifié** du site concerné.
- `--dry-run` par défaut partout ; `--execute` obligatoire pour agir.
- `--site` obligatoire en destructif ; `clean --all` interdit.
- `restore --full` refuse un snapshot **INFECTE** (réinjecterait le malware —
  c'est ce qui s'est passé avec le backup du 3 juillet).
- Snapshots **jamais** écrits sur l'hébergement ; aucun secret en dur.
- **Log horodaté** exhaustif (`mb-backups/mb-remediation.log`, JSONL) → alimente
  le journal d'incident.

## Ce que l'outil ne garantit pas

Un site ayant hébergé un shell root n'est **pas prouvé sain** par un scan : un
backdoor peut être planqué dans un fichier d'apparence normale. Pour la
catégorie A, seule la **reconstruction** (Phase 3) fait foi. L'outil te dit *où*
c'est sale et *vérifie* l'Annexe A après — il ne rend pas le nettoyage
chirurgical sûr.

## Statut de développement

Modules **lecture seule**, **backup/verify/diff/restore** et les **garde-fous**
de `clean` sont implémentés et testés hors-ligne (parsing, intégrité des
snapshots, datation des timestamps, refus de restauration/nettoyage). Les appels
SSH/WP-CLI se valident **contre un vrai site de test** (`dev`/`test`) avant tout
usage sur les sites clients — commence en lecture seule.
