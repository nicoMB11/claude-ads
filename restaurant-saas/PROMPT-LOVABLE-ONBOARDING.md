# Prompt à coller dans Lovable — « Configurer mon restaurant » (onboarding)

> Copie-colle tout ce document dans Lovable. Il s'appuie sur le fichier
> `METHODE-MOTEUR-RESA.md` (la logique du moteur de réservation). Si tu as ce
> fichier, donne-le aussi à Lovable comme référence.

---

## Contexte

Je construis un SaaS de réservation de restaurant (React + Supabase). Le moteur
anti-surbooking raisonne sur des **tables physiques réelles** et des **plages
horaires** (voir `METHODE-MOTEUR-RESA.md`). Je veux ajouter un **parcours
d'installation** (« Configurer mon restaurant ») déclenché depuis le back-office
admin, qui pose au restaurateur toutes les questions nécessaires et configure
automatiquement son établissement.

---

## PARTIE A — Analyse de capacités (à faire MAINTENANT, une seule fois)

**Avant d'écrire le formulaire**, fais l'inventaire des fonctionnalités que les
questions ci-dessous impliquent, et **construis celles qui manquent** dans le
module (schéma Supabase + logique + interface).

⚠️ **Important :** cette analyse est une étape de **construction**, à réaliser
**pendant que tu traites ce prompt**. Ne mets **pas** en place un système qui
referait cette analyse à chaque utilisation par un restaurateur. Une fois les
fonctionnalités présentes, le formulaire se contente de les configurer.

**Méthode attendue :**
1. Pour chaque fonctionnalité de la liste ci-dessous, vérifie si elle existe déjà
   (table Supabase, colonne, logique, écran).
2. Produis un court **rapport « Existe / À créer »**.
3. **Crée entièrement** ce qui manque (base + logique + UI), en respectant la
   méthode du moteur.

**Liste des fonctionnalités à vérifier / créer :**

| # | Fonctionnalité | Ce que ça implique |
|---|---|---|
| 1 | **Tables physiques individuelles** | table Supabase avec, par table : nom, capacité **min** et **max**, zone, **combinable** (oui/non), **active** (oui/non). Éditables une par une. |
| 2 | **Combinaison de tables** | pouvoir asseoir un grand groupe sur plusieurs tables `combinable` réunies, avec un nombre max de tables combinées. |
| 3 | **Services multiples** | plusieurs services par jour de semaine (midi, soir…), chacun avec heure de **début** et **dernière table** acceptée. |
| 4 | **Durée de table** | durée d'occupation d'une table, **par service** + valeur par défaut au niveau restaurant. |
| 5 | **Buffer / battement** | temps de remise en place entre deux groupes sur une même table. |
| 6 | **Pas des créneaux** | espacement des heures proposées (15 / 30 min…). |
| 7 | **DOUBLE SERVICE (simple/double)** | réglage **par service** : soit la table tourne après la durée de table (double), soit une table = un seul groupe pour tout le service (simple). *C'est un point souvent absent : crée-le complètement s'il manque, moteur ET affichage.* |
| 8 | **Plafonds de couverts** | plafond **par créneau** et **par service** (facultatifs), en plus des tables. |
| 9 | **Max personnes en ligne** | au-delà, bascule vers une **demande de groupe** au lieu d'une réservation directe. |
| 10 | **Validation manuelle des groupes** | au-delà d'un seuil, la réservation est acceptée en statut **« en attente »** et doit être validée. |
| 11 | **Horizon de réservation** | nombre de jours max à l'avance. |
| 12 | **Fermetures** | fermeture hebdomadaire (déduite des services) + **fermetures exceptionnelles** par date. |
| 13 | **Statuts de réservation** | confirmée / en attente / installée / annulée / no-show, avec règle claire de ceux qui **occupent** une table. |
| 14 | **Moteur anti-surbooking** | occupation par **plages de temps**, contrainte d'exclusion en base (voir Partie F), calcul des **créneaux disponibles**. |
| 15 | **Tunnel de réservation client** | formulaire client (personnes → date → créneau → coordonnées → confirmation), en page dédiée **et** widget intégrable. |
| 16 | **Demande de groupe / privatisation** | formulaire dédié + suivi dans l'admin. |
| 17 | **Événements** | création d'événements (titre, date, heure, capacité) affichés au client. |
| 18 | **Charte graphique** | couleurs (principale + accent) + logo, appliquées au widget ; saisie manuelle **ou** extraction depuis logo / PDF / URL. |
| 19 | **Notifications** | confirmation client + notification restaurant (peuvent être simulées dans un journal si l'envoi réel n'est pas branché). |
| 20 | **Politique & champs client** | champs requis (nom, téléphone obligatoires ; e-mail optionnel), message/allergies, politique d'annulation. |

À la fin de cette partie, **toutes ces fonctionnalités doivent exister** dans le
module. Le formulaire d'onboarding ne fait que les **remplir**.

---

## PARTIE B — Le bouton et la modale « tout écraser »

1. Dans le **back-office admin**, ajoute un bouton bien visible :
   **« Configurer mon restaurant »**.
2. Au clic, ouvre une **modale de confirmation** avant d'entrer dans le
   formulaire, disant clairement :
   > « Cette configuration va **remplacer entièrement** les réglages actuels de
   > votre restaurant (tables, services, horaires, options). Cette action est
   > irréversible. »
3. Exige une **confirmation explicite** (case à cocher « Je comprends » **ou**
   saisie du nom du restaurant) avant d'activer le bouton « Continuer ».
4. **Sécurité réservations :** si des **réservations futures existent**, préviens-en
   dans la modale et propose un choix : les **conserver** (recommandé) ou les
   supprimer. Ne détruis jamais des réservations futures sans confirmation
   séparée.
5. À la validation finale du formulaire, applique la nouvelle configuration en
   **une seule transaction** (tout ou rien).

---

## PARTIE C — Le formulaire d'onboarding (les questions)

Construis un **assistant multi-étapes** (une section = une étape, avec barre de
progression). Chaque réponse alimente la configuration. Rends les étapes 1 à 4
**obligatoires**, le reste facultatif (avec « Passer »).

**Étape 1 — Établissement :** nom, adresse, téléphone, e-mail de contact, fuseau
horaire, description courte.

**Étape 2 — Jours & horaires :** jours d'ouverture ; midi / soir / les deux ;
pour chaque service, heure de début et heure de dernière table ; horaires
spécifiques selon le jour.

**Étape 3 — La salle (voir Partie E pour l'UI détaillée) :** les tables, leur
capacité min/max, les zones, quelles tables sont combinables.

**Étape 4 — Rythme :** durée de table (midi vs soir), buffer entre groupes,
**double service** (par service), pas des créneaux.

**Étape 5 — Limites :** plafond de couverts par créneau / par service ; max
personnes en ligne ; seuil de validation manuelle ; horizon de réservation.

**Étape 6 — Fermetures :** fermetures exceptionnelles à venir.

**Étape 7 — Côté client :** champs requis, message de confirmation, demande
particulière (allergies), politique d'annulation.

**Étape 8 — Image de marque :** couleurs (manuel ou import logo / PDF / URL),
logo, photos.

**Étape 9 — Options :** événements, demande de groupe, plan de salle, SMS,
mailing, chèques cadeaux, acompte ; points d'intégration (site, page, réseaux).

**Écran final :** récapitulatif clair de tout ce qui va être appliqué, puis
bouton **« Appliquer la configuration »** (déclenche la transaction de la
Partie B).

---

## PARTIE D — Config des tables : individuelle, intuitive, assistée par IA

C'est le point le plus important de l'expérience. À l'étape 3 :

1. **Chaque table est éditable individuellement** : nom, capacité **min**, **max**,
   zone, combinable (oui/non), active (oui/non). Ajouter / dupliquer / supprimer
   une table facilement. Édition en ligne, sans quitter l'écran.
2. **Saisie rapide en langage naturel + analyse IA :** propose un champ où le
   restaurateur **décrit sa salle en une phrase** (ex. *« j'ai 8 tables de 2, 4
   tables de 4, une grande table de 6 et un salon privé de 10 »*). Une **analyse
   IA** transforme cette phrase en **liste de tables structurée** (avec min/max
   proposés), que le restaurateur peut ensuite **ajuster table par table**.
3. **L'IA vérifie la cohérence** et alerte, par exemple :
   - min > max sur une table ;
   - une table dont le max dépasse ce qui est réaliste ;
   - capacité totale incohérente avec le nombre de couverts annoncé ;
   - suggère quelles tables marquer **combinables** pour absorber les grands
     groupes, et prévient s'il n'y a **aucune** solution pour les groupes au-delà
     d'une certaine taille (→ recommander l'option « demande de groupe »).
4. **Aperçu vivant :** affiche en direct le **nombre de tables**, la **capacité
   totale en couverts**, et une représentation simple du plan de salle qui se met
   à jour à chaque modification.
5. **Génération assistée (facultatif) :** un mode « config express » où l'on
   indique des lots (« X tables de N places ») et le plan est généré, puis
   affiné manuellement.

L'objectif : que remplir sa salle soit **rapide et sans erreur**, avec l'IA en
copilote qui structure, vérifie et suggère — mais le restaurateur garde la main
sur chaque table.

---

## PARTIE E — Contraintes techniques (Supabase)

Respecte la méthode du moteur (`METHODE-MOTEUR-RESA.md`), en particulier :

1. **Réserver contre des tables réelles**, jamais contre un simple compteur.
2. **Une seule source de vérité** pour « table occupée / libre » : mets-la
   **côté base** (fonction SQL / RPC), appelée par le moteur **et** par
   l'affichage du plan de salle. Ne duplique jamais ce calcul dans le front.
3. **Occupation en plages de temps** (`tstzrange`) et **contrainte d'exclusion**
   (index GiST + `btree_gist`) empêchant **deux réservations chevauchantes sur
   la même table** — l'anti-surbooking garanti par la base, même en cas de
   réservations simultanées.
4. **Vérifier + écrire dans la même transaction**, avec re-vérification au
   dernier moment.
5. **Dates-heures absolues** (pas de « minutes depuis minuit ») pour gérer
   correctement les services tardifs / après minuit.
6. **Double service :** la seule différence est la plage d'occupation attribuée à
   une table (courte = rotation ; toute la durée du service = un seul groupe).
   Le plan de salle doit refléter exactement la même règle que le moteur.

---

## Livrables attendus

1. Le **rapport « Existe / À créer »** de la Partie A.
2. Les **fonctionnalités manquantes créées** (base + logique + UI).
3. Le **bouton + la modale de confirmation** destructive (Partie B).
4. L'**assistant d'onboarding** multi-étapes (Partie C).
5. La **config des tables individuelle + assistée par IA** (Partie D).
6. Le tout branché sur le **moteur anti-surbooking** conforme (Partie E).
