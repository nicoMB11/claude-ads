# mb-rebuild

**Reconstruire des sites WordPress propres — moteur neuf, contenu préservé et nettoyé.**

Un site WordPress = un **moteur** (remplaçable) + du **contenu** (à préserver).
`mb-rebuild` industrialise le remplacement du moteur et la réinjection *propre* du
contenu, pour qu'aucun backdoor ne voyage d'un ancien site (potentiellement infecté)
vers le site reconstruit.

| On REMPLACE (identique partout, jetable) | On GARDE (ton travail) |
|---|---|
| WordPress core (`wp-admin`, `wp-includes`) | La base de données (design, pages, textes, réglages Elementor) |
| Le code des extensions (Elementor, SEOPress…) | `wp-content/uploads/` (tes images) |
| Le code du thème | |

L'outil tourne **sur ta machine** et pilote un hébergement cible via **SSH + WP-CLI**.
Il ne dépose aucun script sur le serveur, et **tout ce qui écrit est en `--dry-run` par défaut**.

---

## Les 4 règles de sûreté

1. **Aucun fichier de code de l'ancien site n'est copié** — ni core, ni plugins, ni thème.
   Uniquement la base et `uploads/`. C'est ce qui garantit qu'aucun backdoor ne voyage.
2. **On ne réinstalle jamais un plugin absent du catalogue.** Un plugin inconnu est
   *signalé*, jamais installé. Pas de nulled par accident.
3. **La base est traitée avec autant de sérieux que les fichiers** — comptes admin hors
   liste blanche, cron malveillant, options autoloadées avec du code, spam, application
   passwords sont détectés et nettoyés.
4. **Aucune clé de licence en clair dans un fichier versionné.** Le catalogue ne stocke
   que le *nom* de la variable d'environnement ; la valeur vit dans un `.env` non versionné.

---

## Installation

```bash
cd mb-rebuild
pip install -e .            # installe la commande `mb-rebuild`
# ou, sans installer :
python3 -m mb_rebuild --help
```

Dépendances : Python ≥ 3.9, PyYAML, requests, et côté système `ssh` / `scp` / `rsync`
(sur ta machine) plus WP-CLI sur les hôtes distants.

---

## Les 4 modules

### 1. `catalog` — le catalogue d'extensions

Un dossier local, versionné et privé, qui stocke les **sources officielles** de tout ce
que tu utilises. `catalog.yml` liste les slugs, versions et licences ; les gratuits sont
téléchargés depuis wordpress.org, les premium sont des ZIP que tu déposes **une fois**,
depuis le compte éditeur (jamais depuis un site existant).

```bash
mb-rebuild catalog verify   --catalog mb-catalog          # tout se résout à une source officielle ?
mb-rebuild catalog licenses --catalog mb-catalog          # les clés .env sont-elles résolvables ? (valeurs masquées)
mb-rebuild catalog slots    --catalog mb-catalog site-*.yml  # slots de licence couverts vs demandés
mb-rebuild catalog download --catalog mb-catalog --apply  # télécharge les ZIP gratuits officiels
```

Voir `examples/catalog.yml` et `examples/.env.example`.

### 2. `detect` — la sélection (lecture seule)

Lit la base de l'ancien site (plugins actifs + thème actif via WP-CLI) et **génère**
`site-config.yml` en ne retenant **que** les extensions présentes dans ton catalogue.
Tout plugin inconnu (nulled potentiel) est **signalé**, jamais ajouté.

```bash
mb-rebuild detect --source deploy@ancien-site:/var/www/site \
                  --catalog mb-catalog --out site-config.yml
```

### 3. `db-scan` / `db-import` — la base de données

`db-scan` exporte la base de l'ancien site, la stocke (snapshot local horodaté) et la
**scanne**. Détections durcies sur une vraie infection (playbook APC) :

- options autoloadées avec du code (`<?php`, `eval`, `base64`) ;
- **famille `sc_`** (scope-connector : auto-récupération, propagation) — sans jamais
  confondre avec le plugin légitime `wpsc_` ;
- **cron malveillant** `sc_cron_fetch` (intervalle custom `sc_interval`) ;
- **décodage base64 AVANT scan** — un injecteur JS de cloaking était caché encodé en
  base64 dans une option au **nom en hash MD5** ; tous les greps littéraux passaient à
  côté. Signatures après décodage : `yadro`, `counter.yadro.ru`, `data:text/javascript`,
  `bodyNode.remove` ;
- toute option **autoloadée nommée par un hash MD5** (32 hex) ;
- comptes admin hors liste blanche, application passwords, spam et scripts injectés.

```bash
mb-rebuild db-scan --source deploy@ancien-site:/var/www/site \
                   --admin-whitelist admin,marie --report scan.md --apply
```

`db-import` fait la même chose puis, **après ta validation** (`--yes`), importe dans la
cible et auto-remédie ce qui est sûr (cron + `sc_cron_fetch`, options code/`sc_`/hash/
cloaking, application passwords, et — sur demande `--remove-users` — les faux admins,
**supprimés avec leur usermeta et leurs posts réattribués** à un compte légitime via
`--reassign-to`). Il applique aussi le **remplacement de domaine** en mode sérialisation-safe
(`wp search-replace`, indispensable avec Elementor). Le spam de contenu dans `wp_posts` est
*signalé* pour revue manuelle, jamais réécrit.

```bash
mb-rebuild db-import --source deploy@ancien:/var/www/site \
                     --target deploy@neuf:/var/www/site \
                     --admin-whitelist admin --remove-users --reassign-to 1 \
                     --search-replace 'https://ancien.com,https://preprod.example.com' \
                     --search-replace 'http://www.ancien.com,https://preprod.example.com' \
                     --yes --apply
```

### 4. `build` — la reconstruction (l'assemblage)

```bash
mb-rebuild build --site site-config.yml \
                 --target deploy@neuf:/var/www/site \
                 --source-uploads deploy@ancien:/var/www/site/wp-content/uploads \
                 --catalog mb-catalog \
                 --wp-version 6.9 \
                 --db-name wpdb --db-user wpuser --db-pass "$DB_PASS" \
                 --preview-url https://preprod.example.com \
                 --report compliance.md --apply
```

Séquence : `wp core download` officiel (version **épinglable** via `--wp-version`) →
`wp-config` neuf (**salts frais**, `$table_prefix` **repris de l'ancien site**,
`DISALLOW_FILE_EDIT=true`, `WP_AUTO_UPDATE_CORE=false` — cas APC : un plugin premium
ancien incompatible avec le WP majeur suivant, on reste maître des mises à jour) →
extensions du catalogue + licences depuis `.env` → thème → base nettoyée → `uploads/`
rapatrié **et scanné** (tout `.php`/`.phtml` supprimé) → durcissement (Wordfence,
inscriptions fermées) → **override de preview** `WP_HOME`/`WP_SITEURL` (optionnel) →
rapport de conformité avec **checklist des étapes manuelles restantes, site par site**.

### `preview` — l'override de préproduction (hygiène de bascule)

L'override `WP_HOME`/`WP_SITEURL` sert à valider sur une URL de préprod. **L'oubli
classique**, c'est de ne pas le retirer à la bascule — d'où une commande dédiée :

```bash
mb-rebuild preview --target deploy@neuf:/var/www/site --url https://preprod.example.com --apply  # poser
mb-rebuild preview --target deploy@neuf:/var/www/site --clear --apply                            # RETIRER à la bascule
```

### Étapes manuelles (hors périmètre CLI)

Le rapport de fin liste, **pour chaque site**, ce que l'outil ne fait **pas** (phases
E/F/G) : détacher/rattacher le domaine dans le **Manager Infomaniak**, bascule **DNS**,
**SSL**, **Google Search Console**, **2FA**, et le retrait de l'override de preview.

---

## Dry-run par défaut

Toutes les commandes qui écrivent sont en `--dry-run` par défaut : elles **affichent le
plan** sans rien exécuter. Ajoute `--apply` pour exécuter réellement. Exemple de plan :

```
[dry-run] ssh deploy@neuf: wp core download --skip-content --path=/var/www/site
[dry-run] ssh deploy@neuf: wp config shuffle-salts --path=/var/www/site
[dry-run] ssh deploy@neuf: wp plugin install elementor --activate --version=3.30.0 ...
[dry-run] ssh deploy@neuf: wp elementor-pro license activate *** ...   # clé masquée
```

Les clés de licence et mots de passe sont **masqués** partout dans les logs et les rapports.

---

## Ce que l'outil NE fait pas (et pourquoi)

- **Il ne bascule pas le DNS tout seul** — tu vérifies sur une URL de préproduction, puis
  tu bascules à la main.
- **Il ne copie aucun fichier de code de l'ancien site.**
- **Il ne réinstalle jamais un plugin absent du catalogue.**
- **Il ne stocke jamais de clé de licence en clair** dans un fichier versionné.

---

## Développement

```bash
pip install -e ".[dev]"
python3 -m pytest -q          # 45 tests sur la logique pure (catalogue, scan DB, uploads, redaction)
```

Les tests couvrent la logique testable sans serveur (parsing du catalogue, slots de licence,
classification detect, scanner de dump SQL, scanner d'uploads, redaction des secrets). Les
chemins SSH/WP-CLI s'exercent contre un vrai hôte.
