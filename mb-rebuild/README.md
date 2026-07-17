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
**scanne** : options autoloadées avec du code (`<?php`, `eval`, `base64`), cron, comptes
admin hors liste blanche, application passwords, liens spam et scripts injectés.

```bash
mb-rebuild db-scan --source deploy@ancien-site:/var/www/site \
                   --admin-whitelist admin,marie --report scan.md --apply
```

`db-import` fait la même chose puis, **après ta validation** (`--yes`), importe dans la
cible et auto-remédie ce qui est sûr (cron, options avec code, application passwords,
et — sur demande `--remove-users` — les admins rogue). Le spam de contenu dans `wp_posts`
est *signalé* pour revue manuelle, jamais réécrit (ça abîmerait le design à préserver).

```bash
mb-rebuild db-import --source deploy@ancien:/var/www/site \
                     --target deploy@neuf:/var/www/site \
                     --admin-whitelist admin --yes --apply
```

### 4. `build` — la reconstruction (l'assemblage)

```bash
mb-rebuild build --site site-config.yml \
                 --target deploy@neuf:/var/www/site \
                 --source-uploads deploy@ancien:/var/www/site/wp-content/uploads \
                 --catalog mb-catalog --report compliance.md --apply
```

Séquence : `wp core download` officiel → `wp-config` neuf (salts frais,
`DISALLOW_FILE_EDIT`) → extensions du catalogue + licences depuis `.env` → thème → base
nettoyée → `uploads/` rapatrié **et scanné** (tout `.php`/`.phtml` supprimé) → durcissement
(Wordfence, inscriptions fermées) → rapport de conformité + rappels manuels (Search Console, DNS).

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
python3 -m pytest -q          # 34 tests sur la logique pure (catalogue, scan DB, uploads, redaction)
```

Les tests couvrent la logique testable sans serveur (parsing du catalogue, slots de licence,
classification detect, scanner de dump SQL, scanner d'uploads, redaction des secrets). Les
chemins SSH/WP-CLI s'exercent contre un vrai hôte.
