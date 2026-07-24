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
npm test          # 9 tests unitaires du moteur anti-surbooking
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
    engine.js        # moteur anti-surbooking (fonctions pures, testées)
    db.js            # schéma SQLite (une table par option → évolutif)
    repo.js          # accès données + création transactionnelle
    routes/index.js  # API JSON (client + admin)
    server.js        # serveur HTTP + routeur + statique (zéro dépendance)
    seed.js          # restaurant de démonstration
  public/            # web app client, widget, back-office (vanilla JS, zéro build)
  tests/engine.test.js
```

### Pistes d'évolution (multi-tenant, prod)

Multi-restaurant déjà supporté au niveau données (`restaurant_id` + `slug`,
API `?r=<slug>`). Pour la production : authentification back-office (session/JWT),
branchement email/SMS réels (SendGrid, Twilio…) à la place de la boîte d'envoi
simulée, paiement (Stripe) pour l'empreinte/acompte, et migration SQLite →
Postgres si volumétrie.
