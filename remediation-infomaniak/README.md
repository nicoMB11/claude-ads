# Suivi de remédiation — Compromission Infomaniak (compte MB1)

Application de suivi (checklist) pour piloter la remédiation de la compromission
du compte d'hébergement Infomaniak MB1 (650852) — 25 sites WordPress.

## Utilisation

Ouvrir `index.html` dans un navigateur. Rien à installer : c'est un fichier
autonome (HTML + CSS + JS, aucune dépendance externe). La progression est
enregistrée dans le navigateur (`localStorage`) et conservée entre les visites
sur la même machine.

## Deux vues (onglets)

### 1. Par phase
- **Bannière « Phase en cours »** : indique automatiquement la première phase
  non terminée. La Phase 0 (confinement) est signalée comme **bloquante** — tant
  qu'elle n'est pas cochée à 100 %, la porte reste ouverte.
- **Frise des phases** : une pastille par phase (0 → 6) avec son avancement.
- **Cases à cocher** pour chaque item du runbook, groupées par sous-phase, avec
  **progression globale**.

| Phase | Objet |
|---|---|
| 0 | Confinement (rotation des accès — **à la main, bloquant**) |
| 1 | Construction de l'outil `mb-remediation` + cartographie |
| 2 | Éradication (artefacts, persistance, sessions) |
| 3 | Reconstruction propre (sites catégorie A) |
| 4 | Restructuration (isolation, durcissement, sauvegardes) |
| 5 | Obligations légales et clients (RGPD / CNIL) |
| 6 | Surveillance continue |

### 2. Par site (25 sites)
- Les 25 sites regroupés par **catégorie** (A/B/C/D) avec un compteur de sites
  traités par catégorie.
- Pour chaque site, un **statut** sélectionnable :
  À traiter → Sauvegarde INFECTÉ prise → Éradication → Reconstruction →
  Vérifié (Annexe A verte) → Remis en ligne (ou Supprimé).
- Chaque site est **dépliable** et contient sa propre **checklist Annexe A**
  (« site déclaré sain », 15 points) — un site ne repasse « En ligne » qu'une
  fois cette checklist verte.
- ⭐ = sites prioritaires (poeles-cheminees.com, prod.baycake.fr).
- **Import automatique** : le bouton « Importer un rapport `mb-remediation` »
  charge les fichiers JSON produits par l'outil (`mb-out/<site>.report.json` ou
  l'agrégat `_report.all.json`) et **coche l'Annexe A automatiquement** par site
  (les points marqués « vérif. manuelle » restent à cocher à la main). Un site
  dont tous les points automatiques sont verts passe au statut « Vérifié ».

| Cat. | Traitement | Sites |
|---|---|---|
| **A** | Reconstruction complète (webshell) | actprev, ansushi, chardenon, flci, ge-solutions, lcd, prod.baycake.fr ⭐, marbrerie-buisan, poeles-cheminees.com ⭐ |
| **B** | Nettoyage + vérif approfondie | estel, EDLC, apf, mobilierbureauservice, kb |
| **C** | Vérification obligatoire (≠ sain) | cantalauze, 1.mbagency, buisan.fr, candidat, jacqueslechat.fr, locarca |
| **D** | Test / dev (à supprimer) | dev, test, testtplm, tplm, tplm2 |

> « Aucun artefact détecté » ≠ « sain » : l'attaquant avait un accès en écriture
> sur les 25 sites. Aucun site n'est propre sans passer l'Annexe A.

## Limites

> La progression est **locale au navigateur**. Pour un suivi partagé en équipe,
> il faudrait la relier à un stockage commun — non implémenté ici.
