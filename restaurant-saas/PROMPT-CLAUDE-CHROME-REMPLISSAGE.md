# Prompt pour Claude dans Chrome — remplir la config « Le Maïa » (Carcassonne)

> À coller dans Claude pour Chrome, avec la page admin du SaaS de réservation
> ouverte dans l'onglet actif.

---

## Ton rôle

Tu es mon assistant. **Je suis commercial** pour ce SaaS de réservation : j'ai
signé avec le restaurant **« Le Maïa » à Carcassonne** et je suis **en
rendez-vous sur place avec le restaurateur** pour configurer son compte. Tu vas
**remplir le formulaire de configuration à ma place**, dans l'onglet ouvert,
pendant que je suis à côté du restaurateur pour confirmer chaque information.

## Comment tu procèdes

1. Sur la page admin, clique sur **« Configurer mon restaurant »**.
2. Une **modale d'avertissement** va prévenir que cela **écrase la config
   actuelle** : coche la case de confirmation (ou saisis le nom du restaurant si
   demandé), puis continue. S'il y a un avertissement sur des réservations
   futures, **choisis de les conserver** et signale-le-moi.
3. Remplis l'assistant **étape par étape**, avec les données ci-dessous.
4. **À la fin de chaque étape, fais une pause** : résume à voix haute (en texte)
   ce que tu as saisi, pour que je puisse le corriger avec le restaurateur avant
   de passer à la suite.
5. **Ne clique JAMAIS sur « Appliquer la configuration »** (l'écran final) sans
   ma validation explicite. Montre-moi d'abord le récapitulatif complet.
6. Si un champ est **ambigu ou absent** de mes données, **demande-moi** — ne
   devine pas. Les valeurs marquées « (à confirmer) » : saisis-les mais
   signale-les-moi pour que je vérifie avec le restaurateur.

---

## Les données à saisir

### Étape 1 — Établissement
- **Nom :** Le Maïa
- **Adresse :** Carcassonne (11000) — *adresse exacte (à confirmer)*
- **Téléphone :** 04 68 __ __ __ *(à confirmer)*
- **E-mail de contact :** *(à confirmer, ex. contact@lemaia-carcassonne.fr)*
- **Fuseau horaire :** Europe/Paris
- **Description :** Cuisine bistronomique méditerranéenne, cadre convivial.

### Étape 2 — Jours & horaires
- **Ouvert :** du mardi au samedi. **Fermé dimanche et lundi.** *(à confirmer)*
- **Services :** déjeuner **et** dîner.
- **Déjeuner :** premier créneau **12:00**, dernière table **13:30**.
- **Dîner :** premier créneau **19:30**, dernière table **21:30**.

### Étape 3 — La salle (utilise le champ de description en langage naturel)
Saisis cette phrase dans le champ « décrivez votre salle » pour l'analyse IA :
> « 6 tables de 2 personnes, 5 tables de 4, 2 tables de 6 en salle ; une terrasse
> avec 4 tables de 2 ; un salon privé pour 8 personnes. »
- Vérifie ensuite la liste générée **table par table** (capacités min/max).
- **Tables combinables :** les tables de salle oui ; le **salon privé : non
  combinable**. La terrasse : combinable entre elles.
- Contrôle la **capacité totale** affichée et signale-la-moi.

### Étape 4 — Rythme du service
- **Durée de table :** déjeuner **90 min**, dîner **120 min**.
- **Buffer entre deux groupes :** **15 min**.
- **Double service :**
  - Déjeuner → **activé** (rotation, la table peut resservir).
  - Dîner → **désactivé** (une table = un seul groupe pour la soirée).
- **Pas des créneaux :** **15 min**.

### Étape 5 — Limites
- **Plafond de couverts / service au dîner :** **45** *(à confirmer)*. Déjeuner :
  pas de plafond.
- **Max personnes en réservation en ligne :** **10** (au-delà → demande de groupe).
- **Seuil de validation manuelle :** à partir de **8** personnes.
- **Horizon de réservation :** **60 jours**.

### Étape 6 — Fermetures
- Aucune fermeture exceptionnelle pour l'instant. *(demande au restaurateur ses
  prochains congés / jours fériés fermés et ajoute-les si besoin.)*

### Étape 7 — Côté client
- **Champs requis :** nom + téléphone obligatoires ; e-mail facultatif.
- **Demande particulière / allergies :** activée.
- **Politique d'annulation :** merci de prévenir au moins **24 h** à l'avance.
- **Message de confirmation :** « Merci, votre table au Maïa est confirmée. À très
  bientôt ! »

### Étape 8 — Image de marque
- **Logo :** si le restaurateur en a un sous la main, importe-le et laisse l'outil
  en extraire les couleurs ; sinon passe en saisie manuelle.
- **Couleurs par défaut (méditerranéen) si pas de logo :** principale bleu profond
  **#1F5673**, accent ocre/terracotta **#C4753A**. *(à ajuster avec le
  restaurateur)*

### Étape 9 — Options à activer
- **Réservation d'événements :** oui.
- **Demande de privatisation / groupe :** oui.
- **Plan de salle digital :** oui.
- SMS / mailing / chèques cadeaux / acompte : **non pour l'instant** *(à revoir
  ensemble plus tard)*.
- **Intégration :** bouton de réservation sur le site du restaurant + page dédiée.

---

## Rappels de comportement
- Avance **étape par étape**, pause + résumé à chaque étape.
- **Demande-moi** dès qu'une info manque ou semble incohérente.
- **N'applique pas** la configuration finale sans mon feu vert.
- Tout ce qui est « (à confirmer) » : signale-le-moi clairement à la fin.
