# Resa SaaS — démo de réservation restaurant (type Zenchef)

Démo **fonctionnelle** d'un SaaS de réservation pour restaurant, avec un moteur
**anti-surbooking** basé sur le plan de salle réel (tables / chaises), un espace
client (site + web app), un widget embarquable et un back-office restaurant
entièrement configurable.

> Conçu pour être **évolutif** : chaque option de la grille tarifaire est un
> module isolé (activable/désactivable), le socle de base fonctionne seul.
> Les connexions externes (email / SMS) sont **simulées** (boîte d'envoi interne)
> comme demandé pour la démo.

## Démarrage

```bash
cd restaurant-saas
npm run seed      # crée la base SQLite + un restaurant de démonstration
npm start         # démarre le serveur sur http://localhost:3000
```

Aucune dépendance à installer : tout tourne sur les modules natifs de Node
(`node:sqlite`, `node:http`). **Node ≥ 22.5** requis.

| Surface | URL |
|---|---|
| Réservation client (web app mobile / tél.) | http://localhost:3000/ |
| Back-office restaurant | http://localhost:3000/admin.html |
| Widget embarqué sur un site vitrine (démo) | http://localhost:3000/embed-demo.html |
| Widget seul (iframe) | http://localhost:3000/book.html |

```bash
npm test          # 11 tests unitaires (anti-surbooking, double service, capacités)
```

## Le moteur anti-surbooking (cœur du produit)

Une réservation n'est acceptée que s'il existe, **pour toute la durée du repas**,
une ou plusieurs table(s) physique(s) réellement libre(s) pouvant accueillir le
groupe. La capacité physique du restaurant est donc la **limite dure** → le
surbooking est structurellement impossible.

Trois contraintes cumulatives (`server/engine.js`) :

1. **Assignation de table** — recherche d'une table libre couvrant
   `[heure, heure + durée]` (+ buffer de remise en place), avec **combinaison de
   tables** (tables « joignables ») pour les grands groupes.
2. **Plafond de couverts par créneau** *(optionnel, par service)*.
3. **Plafond de couverts par service** *(optionnel, par service)*.

L'écriture se fait dans une **transaction** qui re-vérifie la disponibilité au
dernier moment → pas de course entre deux clients simultanés.

Réglable par restaurant : nombre et taille des tables, zones, durée moyenne d'un
repas, buffer entre services, pas des créneaux, horizon de réservation,
capacité par créneau/service.

### Double service (rotation des tables)

Configurable **par service** dans l'onglet *Configuration* :

- **Durée de service** : plage `début → dernier créneau`.
- **Durée de table** : temps d'occupation d'une table (`turn time`), surchargeable
  par service.
- **Double service autorisé** (bascule) :
  - **activé** → une table peut être ré-attribuée dans le même service dès qu'elle
    se libère (après la durée de table + buffer) → plusieurs passages / rotation ;
  - **désactivé** → une table = **un seul groupe pour tout le service** (pas de
    second passage), même si la durée de table est écoulée.

Le plan de salle et le moteur partagent exactement la même logique d'occupation
(`occupiedTables` dans `engine.js`) → l'affichage reflète toujours la règle
appliquée. *Exemple livré : déjeuner en double service, dîner en simple service.*

## Configuration restaurant (back-office)

- **Tables & couverts** : ajout unitaire ou **config express** (« 6 tables de 2,
  6 tables de 4, 2 tables de 6 » → plan généré).
- **Services & horaires** : par jour de semaine, premier/dernier créneau,
  plafonds de couverts, durée de repas par service.
- **Fermetures exceptionnelles**.
- **Plan de salle digital** : occupation temps réel à une date/heure donnée.
- **Réservations** : consultation, prise de réservation téléphone, statuts
  (confirmée / à valider / installée / annulée / no-show).
- **Boîte d'envoi simulée** : trace les notifications restaurant + confirmations
  client (remplace mail/SMS réels en démo).

## Charte graphique (personnalisation des couleurs)

Onglet *Charte* du back-office. Les couleurs choisies s'appliquent en temps réel
au widget et à la web app client (variables CSS injectées via `applyBranding`).
Quatre méthodes de saisie, **offline sauf la dernière** :

| Méthode | Fonctionnement | Connexion |
|---|---|---|
| **Nuancier HEX manuel** | color pickers + champs HEX, aperçu live | aucune |
| **Import logo / image** | extraction des couleurs dominantes dans le navigateur (canvas) | aucune |
| **Import charte PDF (DA)** | lecture des opérateurs couleur du PDF (`rg`/`k`/hex), flux dé-compressés via `DecompressionStream` natif | aucune |
| **Lien du site** | le serveur récupère la page + CSS et extrait la palette (`server/colors.js`, garde-fou anti-SSRF) | **internet requis** |

Chaque extraction propose des pastilles cliquables → applique la couleur à la
*principale* ou à l'*accent* (sélecteur). En démo « ouverte » sans réseau, seule
la lecture par URL est indisponible et échoue proprement ; les trois autres
fonctionnent hors-ligne.

## Correspondance avec l'offre

**Inclus dans l'offre de base** — formulaire de réservation personnalisé,
sélection date/horaire/couverts, infos client (nom, tél., email), message,
paramétrage jours/horaires/services, gestion des capacités par créneau **ou**
par service, notification restaurant, email de confirmation (simulés), tableau
de bord admin, intégration sur site, optimisation mobile.

**Options complémentaires** (module activable dans l'onglet *Options*) :

| Option | État dans la démo |
|---|---|
| Plan de salle digital | ✅ implémenté (onglet Plan de salle) |
| Réservation d'événements | ✅ implémenté (création + affichage client) |
| Demande de privatisation / groupe | ✅ implémenté (formulaire + back-office) |
| Validation groupe au-delà d'un seuil | ✅ implémenté (seuil réglable) |
| Empreinte bancaire / acompte | ⚙️ flag activable (paiement non branché en démo) |
| SMS de rappel / avis, mailing | ⚙️ flag activable (envoi simulé) |
| Chèques cadeaux en ligne | ⚙️ flag activable |

## Intégration sur un site (comme Zenchef / TheFork)

```html
<div id="resa-widget"></div>
<script src="https://VOTRE-DOMAINE/embed.js"
        data-restaurant="petit-comptoir"
        data-target="#resa-widget"></script>
```

Le widget s'affiche dans une iframe isolée (styles du site non impactés).
Voir `public/embed-demo.html` pour un exemple en contexte.

## Architecture

```
restaurant-saas/
  server/
    engine.js        # moteur anti-surbooking + double service (fonctions pures, testées)
    db.js            # schéma SQLite + migrations additives (une table par option → évolutif)
    repo.js          # accès données + création transactionnelle
    colors.js        # extraction de palette depuis une URL (seul module réseau)
    routes/index.js  # API JSON (client + admin)
    server.js        # serveur HTTP + routeur + statique (zéro dépendance)
    seed.js          # restaurant de démonstration
  public/
    js/palette.js    # extraction couleurs logo/PDF côté navigateur (offline)
    ...              # web app client, widget, back-office (vanilla JS, zéro build)
  tests/engine.test.js   # 11 tests (anti-surbooking, double service, capacités)
```

### Pistes d'évolution (multi-tenant, prod)

Multi-restaurant déjà supporté au niveau données (`restaurant_id` + `slug`,
API `?r=<slug>`). Pour la production : authentification back-office (session/JWT),
branchement email/SMS réels (SendGrid, Twilio…) à la place de la boîte d'envoi
simulée, paiement (Stripe) pour l'empreinte/acompte, et migration SQLite →
Postgres si volumétrie.
