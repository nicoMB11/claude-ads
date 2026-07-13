# Suivi de remédiation — Compromission Infomaniak (compte MB1)

Application de suivi (checklist) pour piloter la remédiation de la compromission
du compte d'hébergement Infomaniak MB1 (650852) — 25 sites WordPress.

## Utilisation

Ouvrir `index.html` dans un navigateur. Rien à installer : c'est un fichier
autonome (HTML + CSS + JS, aucune dépendance externe).

## Ce que fait l'appli

- **Bannière « Phase en cours »** : indique automatiquement la première phase
  non terminée. La Phase 0 (confinement) est signalée comme **bloquante** — tant
  qu'elle n'est pas cochée à 100 %, la porte reste ouverte.
- **Frise des phases** : une pastille par phase (0 → 6) avec son avancement.
  Cliquer déplie la phase correspondante.
- **Progression globale** en haut à droite.
- **Cases à cocher** pour chaque item du runbook, groupées par sous-phase.
- **Persistance** : l'avancement est enregistré dans le navigateur
  (`localStorage`), donc conservé entre les visites sur la même machine.
- **Réinitialiser** / **Tout replier** dans la barre du bas.

## Contenu

Les phases reprennent le runbook de remédiation v2 :

| Phase | Objet |
|---|---|
| 0 | Confinement (rotation des accès — **à la main, bloquant**) |
| 1 | Construction de l'outil `mb-remediation` + cartographie |
| 2 | Éradication (artefacts, persistance, sessions) |
| 3 | Reconstruction propre (sites catégorie A) |
| 4 | Restructuration (isolation, durcissement, sauvegardes) |
| 5 | Obligations légales et clients (RGPD / CNIL) |
| 6 | Surveillance continue |

> La progression est **locale au navigateur**. Pour un suivi partagé en équipe,
> il faudrait la relier à un stockage commun — non implémenté ici.
