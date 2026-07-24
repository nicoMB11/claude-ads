# Méthode d'un moteur de réservation restaurant (sans surbooking)

> Ce document explique **la méthode et le raisonnement** derrière un moteur de
> réservation de restaurant. Il ne contient pas de code réutilisable : il est
> écrit pour qu'une autre personne (ou une autre IA) puisse **reconstruire un
> moteur équivalent** dans n'importe quel environnement — ici visé : **Lovable +
> Supabase**, c'est-à-dire **React** (les écrans) et **PostgreSQL** (la base de
> données).
>
> Il peut aussi servir de base à un **cahier des charges**.
>
> Quelques mots de vocabulaire, expliqués une fois pour toutes :
> - **Créneau** : une heure proposée à la réservation (12:00, 12:15, 12:30…).
> - **Service** : une période d'ouverture (le déjeuner, le dîner…).
> - **Couvert** : une personne attablée. « 40 couverts » = 40 personnes.
> - **Durée de table** (ou « rotation ») : combien de temps un groupe occupe sa
>   table avant qu'on puisse la redonner à quelqu'un d'autre.
> - **Buffer** (ou « battement ») : petit temps de remise en place entre deux
>   groupes sur une même table (débarrasser, redresser).

---

## 1. Le principe anti-surbooking, expliqué simplement

**Le cœur du moteur tient en une phrase :** on n'accepte une réservation **que
s'il existe une vraie table libre, physiquement, pendant toute la durée du
repas.** Pas de compteur abstrait de « places restantes » : on raisonne sur les
**tables réelles** du restaurant.

Concrètement, quand quelqu'un demande « une table pour 4, samedi à 20h », le
moteur regarde toutes les tables du restaurant, retire celles déjà prises à ce
moment-là, et cherche parmi celles qui restent une table (ou une combinaison de
tables) capable d'accueillir 4 personnes. **S'il n'en trouve aucune, la
réservation est refusée.** S'il en trouve une, il la réserve nommément pour ce
groupe.

**Pourquoi le surbooking devient structurellement impossible :** parce que la
limite n'est pas un nombre qu'on a saisi quelque part (« on accepte 50 couverts
par soir ») — un nombre pareil peut être faux, oublié, mal réglé. La limite,
c'est **le nombre de tables qui existent vraiment**. On ne peut pas attribuer
deux fois la même table sur le même horaire, exactement comme on ne peut pas
asseoir deux groupes différents sur la même chaise en même temps. Le monde
physique fait office de garde-fou.

C'est la différence clé avec un système « à quotas » : un quota, on peut le
dépasser par erreur ; **une table déjà occupée, on ne peut pas la dédoubler.**

> 💡 **À retenir pour la reconstruction :** ne jamais réserver contre un
> compteur global. Toujours réserver contre **une table nommée**. Le compteur de
> couverts peut exister *en plus* (voir §5), mais il ne doit jamais être la
> seule barrière.

---

## 2. Le modèle de données

Voici les « tableaux de données » (en base : des **tables SQL** ; à ne pas
confondre avec les tables du restaurant) et à quoi chacun sert.

### 2.1 Les entités

| Donnée | Rôle |
|---|---|
| **Restaurant** | L'établissement. Porte les réglages généraux (durée de table par défaut, buffer, pas des créneaux, horizon de réservation, nombre max de personnes en ligne…). |
| **Table physique** (le mobilier) | Une vraie table de la salle. C'est l'unité de base contre laquelle on réserve. |
| **Service** | Une période d'ouverture récurrente (ex. « Déjeuner, le mardi, de 12:00 à 13:45 »). Définit *quand* on peut réserver et avec quelles règles. |
| **Fermeture exceptionnelle** | Une date où le restaurant est fermé malgré les services habituels (jour férié, congés). |
| **Réservation** | Une demande acceptée : qui, combien, quand, pour combien de temps, et **sur quelle(s) table(s)**. |

À cela s'ajoutent, selon les options : **événements**, **demandes de groupe /
privatisation**, et une **boîte d'envoi** (journal des e-mails/SMS qui *seraient*
envoyés — en démo ils ne partent pas vraiment).

### 2.2 Les liens entre elles

Tout tourne autour du restaurant :

```
Restaurant  1 ──< Tables physiques
Restaurant  1 ──< Services
Restaurant  1 ──< Fermetures
Restaurant  1 ──< Réservations
Réservation ──> une ou plusieurs Tables physiques   (l'attribution)
```

Le lien le plus important est le dernier : **une réservation référence les
tables qui lui sont attribuées.** C'est ce lien qui matérialise « cette table
est prise par ce groupe ». Un grand groupe peut pointer vers **plusieurs**
tables (voir combinaisons, §3).

> ⚠️ En PostgreSQL / Supabase, deux façons de stocker l'attribution :
> - une **table de liaison** `reservation_tables (reservation_id, table_id)` —
>   c'est l'approche « propre » recommandée, une ligne par table attribuée ;
> - ou un tableau d'identifiants dans la réservation.
>
> **Préférez la table de liaison** : elle permet de poser des contraintes
> solides en base (voir §6, la contrainte anti-chevauchement).

### 2.3 Les champs qui ne sont pas évidents (et pourquoi ils existent)

**Sur une table physique :**
- `capacité min` et `capacité max` (nombre de couverts). On garde **deux**
  valeurs, pas une seule : le *max* dit combien de personnes tiennent, le *min*
  évite de gâcher une grande table pour 2 personnes quand ce n'est pas
  souhaitable. En pratique, pour décider si un groupe *rentre*, on regarde le
  **max**.
- `combinable` (oui/non). Certaines tables peuvent être rapprochées pour former
  une grande tablée (voir §3) ; d'autres non (une table déjà isolée, un salon
  privé). Ce champ dit lesquelles.
- `zone` (Salle, Terrasse, Salon privé…). Sert à l'affichage et pourrait servir
  à des règles par zone.
- `active` (oui/non). Pour retirer temporairement une table sans la supprimer
  (travaux, table cassée) sans perdre l'historique.

**Sur un service :**
- `jour de la semaine` + `heure de début` + `dernier créneau`. On sépare le
  **début du service** du **dernier créneau réservable** : on peut ouvrir à
  19:00 mais ne plus accepter de nouvelle table après 21:30.
- `durée de table` (spécifique au service). Le déjeuner tourne vite (90 min), le
  dîner est plus long (105 min). D'où une durée **par service**, avec une valeur
  par défaut au niveau du restaurant si on ne précise rien.
- `double service autorisé` (oui/non) — **le champ le plus subtil**, expliqué en
  détail au §4.
- `plafond de couverts par créneau` et `par service` (facultatifs). Limites
  *en plus* des tables, voir §5.

**Sur une réservation :**
- `date` + `heure` + `durée`. On stocke la **durée** au moment de la réservation
  (copiée depuis le service). Ainsi, si on change plus tard la durée de table du
  service, les réservations déjà prises ne bougent pas.
- `tables attribuées`. **On attribue la table dès la réservation**, on ne
  l'improvise pas le jour J. C'est ce qui rend le refus fiable.
- `statut` (confirmée / en attente de validation / installée / annulée /
  no-show). Seuls certains statuts « occupent » réellement une table (une
  annulée ne compte plus).
- `source` (site, widget, téléphone, back-office). Utile pour savoir d'où vient
  la résa, sans effet sur le moteur.

---

## 3. L'algorithme d'attribution d'une table, étape par étape

Quand une demande arrive (« X personnes, telle date, telle heure »), le moteur
déroule **toujours le même enchaînement**, dans cet ordre :

### Étape 1 — Le restaurant est-il ouvert à ce moment ?
- La date n'est pas dans le passé, et pas au-delà de l'horizon de réservation.
- La date n'est pas une **fermeture exceptionnelle**.
- Il existe un **service** qui couvre ce jour de la semaine **et** dont la plage
  contient l'heure demandée.
- Si l'une de ces conditions échoue → **refus « fermé »**.

### Étape 2 — Quelle est la fenêtre d'occupation demandée ?
- On récupère la **durée de table** du service concerné.
- La réservation occupera donc la plage : **[heure de début → heure de début +
  durée]**, à laquelle on ajoutera le **buffer** au moment de comparer.

  *Exemple : 20:00, durée 105 min → occupe de 20:00 à 21:45 (+ buffer).*

### Étape 3 — Quelles tables sont déjà prises sur cette fenêtre ?
- On liste toutes les réservations **actives** du même jour.
- Pour chacune, on calcule **sa** plage d'occupation (attention : elle dépend du
  réglage double service, voir §4).
- Si sa plage **chevauche** la fenêtre demandée, ses tables sont marquées
  « occupées ».

  **La notion de chevauchement** (le point technique central, mais simple) :
  deux plages horaires se chevauchent si **l'une commence avant que l'autre ne
  finisse, et réciproquement**. Autrement dit, elles se chevauchent *sauf* si
  l'une est entièrement avant l'autre.

  > Règle mémo : `débutA < finB` **ET** `débutB < finA` → elles se chevauchent.
  >
  > *20:00–21:45 et 21:00–22:45 se chevauchent (elles partagent 21:00–21:45).
  > 20:00–21:45 et 21:45–23:30 ne se chevauchent pas (elles se touchent sans se
  > superposer).*

  C'est le **buffer** qu'on ajoute à la fin de chaque occupation existante pour
  laisser le temps de remettre la table en place avant le groupe suivant.

### Étape 4 — Reste-t-il de quoi asseoir le groupe ?
On prend toutes les tables **actives et non occupées**, puis on cherche une
attribution, dans cet ordre de préférence :

1. **Une seule table qui convient, la plus petite possible.** Parmi les tables
   dont la capacité max ≥ taille du groupe, on prend **celle qui gaspille le
   moins de sièges**. Pourquoi la plus petite ? Pour **garder les grandes tables
   libres** au cas où un grand groupe arriverait ensuite. Mettre 2 personnes sur
   une table de 6 « brûle » une ressource rare.

2. **Sinon, une combinaison de tables** (uniquement parmi les tables
   `combinable`). On additionne les capacités de plusieurs tables voisines
   jusqu'à atteindre la taille du groupe. On plafonne le nombre de tables
   combinées (par ex. 3 max) pour rester réaliste.

3. **Si rien ne convient → refus « complet ».**

### Étape 5 — Les plafonds de couverts sont-ils respectés ? (facultatif)
Si le service a un plafond « par créneau » ou « par service » (voir §5), on
vérifie qu'en ajoutant ce groupe on ne le dépasse pas. Sinon → refus.

### Étape 6 — On écrit la réservation, en une seule opération sûre
On enregistre la réservation **et** son attribution de tables **dans la même
transaction**, en **re-vérifiant la disponibilité juste avant d'écrire** (voir le
piège de la double réservation au §6).

> 💡 **Pour proposer des créneaux (et pas seulement accepter/refuser) :** pour
> afficher au client les heures disponibles d'une journée, on **rejoue l'étape 2
> à 5 pour chaque créneau** de chaque service (12:00, 12:15, 12:30…) et on marque
> chacun « libre » ou « complet ». C'est exactement le même calcul, répété.

---

## 4. La gestion du double service (simple vs double)

C'est **le réglage le plus délicat**, et celui qui provoque le plus d'erreurs si
on le traite naïvement. Il se règle **par service**.

### La différence, concrètement

Tout se joue sur **la durée pendant laquelle une table reste bloquée** une fois
qu'un groupe y est assis.

- **Double service AUTORISÉ** (rotation) : la table se libère **dès que le repas
  est fini** (heure de début du groupe + durée de table + buffer). On peut donc
  la **redonner à un autre groupe plus tard dans le même service**.

  *Exemple (dîner en rotation, durée 90 min) : un groupe arrive à 19:00, il
  occupe la table de 19:00 à 20:30. À partir de 20:30, la table est de nouveau
  proposable — un deuxième groupe peut la prendre à 20:45.*

- **Double service NON AUTORISÉ** (un seul passage) : la table est bloquée
  **pour toute la durée du service**, quelle que soit la durée de table. Une
  table = **un seul groupe pour la soirée**. On ne la reproposera pas, même une
  fois le premier repas théoriquement terminé.

  *Exemple (dîner en simple service) : le groupe de 19:00 « garde » sa table
  jusqu'à la fin du service. Même à 21:30, la table reste indisponible pour un
  nouveau groupe.*

### Ce qui change dans le calcul

La **seule chose** qui change, c'est la **plage d'occupation** attribuée à une
réservation existante quand on cherche les tables libres (étape 3 du §3) :

- En **double service** : plage = `[début → début + durée de table + buffer]`
  (courte, la table tourne).
- En **simple service** : plage = `[début du service → fin du service + buffer]`
  (longue, la table est prise toute la période).

Rien d'autre ne bouge. Tout le reste de l'algorithme est identique.

### Pourquoi c'est un piège — et l'erreur que j'ai dû corriger

Le calcul « une table est-elle occupée ? » est utilisé à **deux endroits** :
1. par le **moteur**, quand il décide d'accepter ou refuser une réservation ;
2. par l'**écran plan de salle**, quand il colore les tables occupées à une
   heure donnée.

**L'erreur classique (que j'ai commise puis corrigée) :** j'avais codé ce calcul
**deux fois**, une fois dans le moteur et une fois dans l'affichage. Le moteur
appliquait bien la règle du double service ; l'affichage, lui, utilisait un
calcul plus simple (toujours basé sur la durée de table). Résultat : en simple
service, le **moteur** bloquait bien une table toute la soirée, mais le **plan de
salle** l'affichait « libre » passé la durée du repas. Les deux se
**contredisaient** — un cauchemar pour se faire confiance, et un bug très
difficile à repérer parce que chaque écran, pris seul, semblait « marcher ».

**La correction :** j'ai extrait ce calcul dans **une seule fonction partagée**
(« quelles tables sont occupées sur telle fenêtre ? ») utilisée **à la fois** par
le moteur et par l'affichage. Une seule source de vérité.

> 🔑 **Conseil n°1 de tout ce document :** la logique « table occupée ou
> libre ? » doit exister **à un seul endroit** et être appelée partout. Ne la
> réécrivez jamais dans l'affichage. Dans une architecture Supabase, l'idéal est
> de la mettre **côté base de données** (une fonction SQL / RPC, ou carrément une
> contrainte, voir §6), pour que ni le front React ni aucun autre client ne
> puisse en avoir une version divergente.

---

## 5. Les réglages configurables par restaurant

Un moteur « évolutif » doit être **paramétrable sans toucher au code**. Voici
tout ce qui doit être réglable, et l'effet concret de chaque réglage.

| Réglage | Niveau | Effet concret |
|---|---|---|
| **Pas des créneaux** (ex. 15 min) | Restaurant | Espacement des heures proposées (12:00, 12:15…). Plus fin = plus de choix, mais plus de créneaux à calculer. |
| **Durée de table** (ex. 90 min) | Restaurant (défaut) + par service | Combien de temps un groupe garde sa table. Plus court = plus de rotations possibles = plus de couverts sur la soirée. |
| **Durée / plage de service** (début → dernier créneau) | Service | Quand commence et jusqu'à quand on peut réserver. Sépare « on ouvre à 19h » de « dernière table à 21h30 ». |
| **Double service** (oui/non) | Service | Voir §4. Autorise ou non de redonner une table dans le même service. |
| **Buffer / battement** (ex. 10 min) | Restaurant | Temps de remise en place entre deux groupes sur une même table. Augmente la « vraie » durée d'occupation. |
| **Plafond de couverts par créneau** | Service | Limite le nombre de personnes qui arrivent **à la même heure** (pour ne pas noyer la cuisine à 20:00 pile), même s'il reste des tables. |
| **Plafond de couverts par service** | Service | Limite le total de personnes sur toute la période (capacité cuisine sur la soirée). |
| **Nombre max de personnes en ligne** (ex. 12) | Restaurant | Au-delà, on bascule vers une **demande de groupe** (validation manuelle) plutôt qu'une réservation directe. |
| **Horizon de réservation** (ex. 60 jours) | Restaurant | Jusqu'à combien de jours à l'avance on peut réserver. |
| **Seuil de validation groupe** (ex. 8) | Restaurant | À partir de X personnes, la réservation est acceptée mais **« en attente »** : le restaurant doit la valider. |
| **Le plan de salle lui-même** | Restaurant | Nombre de tables, capacité de chacune, zone, combinables ou non. C'est **la** capacité réelle. |

> Les plafonds de couverts sont une **sécurité en plus** des tables, pas à la
> place. Exemple : vous avez assez de tables pour 60 personnes, mais votre
> cuisine ne suit pas au-delà de 40 en même temps → plafond de service à 40.

---

## 6. Les pièges et cas limites (la partie la plus précieuse)

Voici **tout ce qui peut faire échouer une reconstruction naïve**. Chaque point =
un problème réel + sa solution.

### 6.1 Deux clients réservent la dernière table en même temps
**Problème :** deux personnes demandent la même table à la même seconde. Si on
fait « je vérifie que c'est libre » puis (un instant plus tard) « j'enregistre »,
les deux vérifications peuvent réussir avant qu'aucune n'ait écrit → **double
réservation**, exactement ce qu'on voulait empêcher.

**Solution :** la vérification et l'écriture doivent être **une seule opération
indivisible** (une transaction), et il faut **re-vérifier la disponibilité au
tout dernier moment**, à l'intérieur de la transaction, juste avant d'écrire.

**En PostgreSQL / Supabase — la bonne façon**, bien plus robuste que dans un
petit serveur maison : posez une **contrainte d'exclusion** en base. PostgreSQL
sait empêcher, au niveau de la base elle-même, que **deux réservations se
chevauchent sur la même table**. On modélise l'occupation comme une **plage de
temps** (`tstzrange`) et on déclare une contrainte qui **rejette
automatiquement** tout chevauchement sur une même table (via un index `GiST` et
l'extension `btree_gist`). Résultat : **même en cas de course**, la base refuse
la seconde écriture. C'est le « surbooking structurellement impossible » rendu
absolu, garanti par le moteur de base de données et pas seulement par votre code.

> C'est sans doute **le meilleur cadeau que vous fait Postgres** pour ce projet.
> Faites-en le socle.

### 6.2 Les grands groupes qui ne tiennent sur aucune table
**Problème :** un groupe de 10 alors que la plus grande table fait 6.

**Solution :** les **combinaisons de tables** (§3, étape 4). Mais attention :
- ne combinez que les tables marquées `combinable` (un salon privé ou une table
  isolée ne se rapproche pas d'une autre) ;
- **plafonnez** le nombre de tables combinées (assembler 6 tables pour un groupe
  n'a pas de sens en salle) ;
- au-delà d'un certain nombre de personnes, **ne réservez pas automatiquement** :
  basculez vers une **demande de groupe** validée à la main. On ne veut pas qu'un
  robot bloque la moitié de la salle sans qu'un humain confirme.

### 6.3 Le choix de la table : ne prenez pas la première venue
**Problème :** si on attribue la première table libre trouvée, on peut coller un
couple sur une table de 6 et refuser un groupe de 6 dix minutes plus tard.

**Solution :** toujours attribuer **la plus petite table qui convient** (celle
qui gaspille le moins de sièges). On préserve les grandes tables pour ceux qui en
ont besoin. C'est une règle simple mais qui change beaucoup le taux de
remplissage.

### 6.4 Incohérence moteur ⇄ affichage
Déjà raconté au §4 : **le même calcul dupliqué à deux endroits finit par
diverger.** Une seule source de vérité. Je le remets ici parce que c'est le
piège qui coûte le plus cher en confiance.

### 6.5 Les services qui finissent après minuit
**Problème :** un dîner dont le dernier créneau est 23:30 avec une durée de
90 min « déborde » sur le lendemain (01:00). Si vous représentez les heures comme
un simple nombre de minutes depuis minuit (0 à 1440) **rattaché à une seule
date**, une occupation qui passe minuit « repart à zéro » et vos comparaisons de
chevauchement deviennent fausses.

**Solution recommandée pour la reconstruction :** ne raisonnez pas en
« minutes dans la journée » mais en **dates-heures absolues** (un vrai
horodatage début + un vrai horodatage fin). PostgreSQL gère nativement ça avec le
type **plage d'horodatage** (`tstzrange`), et le chevauchement devient trivial et
correct même à cheval sur minuit. C'est une raison de plus d'adopter l'approche
« plages de temps » de Postgres dès le départ, plutôt que de recalculer des
minutes à la main comme dans un prototype.

### 6.6 Fuseaux horaires et changements d'heure
**Problème :** « 20:00 » n'a de sens que dans le fuseau du restaurant. Un calcul
en heure serveur (souvent UTC) décale tout, et les week-ends de changement
d'heure créent des trous ou des doublons.

**Solution :** stockez et raisonnez dans le **fuseau du restaurant**, et fixez-le
explicitement (par ex. `Europe/Paris`). Convertissez à l'affichage, pas dans la
logique. Dans mon prototype j'ancrais volontairement le calcul du jour de la
semaine à midi pour éviter qu'un décalage de fuseau ne fasse « glisser » une
réservation au mauvais jour — c'est le genre de détail qui vous mord.

### 6.7 Statuts de réservation : lesquels « occupent » une table ?
**Problème :** si vous comptez toutes les réservations comme occupantes, une
**annulée** continue de bloquer une table (fantôme). Si vous n'en comptez pas
assez, vous surbookez.

**Solution :** définissez clairement les statuts **actifs** (confirmée, en
attente de validation, installée) qui occupent une table, versus les **inactifs**
(annulée, no-show) qui ne comptent plus. **Une réservation « en attente de
validation » doit occuper la table** pendant sa validation, sinon vous risquez de
la promettre deux fois.

### 6.8 Modifier une réservation existante
**Problème :** quand on **modifie** une résa (changer l'heure), la vérification
de disponibilité voit l'ancienne version d'elle-même et croit que « c'est
complet ».

**Solution :** lors d'une modification, **excluez la réservation en cours** du
calcul d'occupation. (Dans mon moteur, un paramètre « ignore cet identifiant »
servait à ça.)

### 6.9 Le buffer oublié
**Problème :** sans battement entre deux groupes, vous enchaînez une table à la
seconde près, ce qui est irréaliste (il faut débarrasser).

**Solution :** ajoutez le buffer **à la fin de l'occupation existante** avant de
tester le chevauchement. Petit détail, gros confort en salle.

### 6.10 Fermetures et exceptions
**Problème :** un service récurrent (« dîner le vendredi ») ne sait pas qu'un
vendredi précis est férié.

**Solution :** une liste de **fermetures exceptionnelles** par date, testée
**avant** tout le reste. Prévoyez aussi, à terme, des horaires exceptionnels
(ouverture spéciale un jour normalement fermé).

---

## 7. Les surfaces (écrans) et ce qu'elles font

Fonctionnellement, il y a **trois familles d'écrans**.

### 7.1 Côté client (celui qui réserve)
- **Le tunnel de réservation** (3 étapes) : on choisit **combien de personnes**
  et **quelle date** → le système affiche les **créneaux réellement disponibles**
  (les complets sont grisés) → on choisit une heure → on saisit ses coordonnées
  (nom, téléphone, e-mail, message) → **confirmation** avec une référence.
- **La web app / page de réservation** : la même chose, présentée comme une
  page autonome (idéale sur mobile, pour les réservations par téléphone que le
  restaurant saisit lui-même, ou pour un lien direct). Elle montre aussi les
  infos du restaurant, les **événements** à venir, et un **formulaire de demande
  de groupe / privatisation** pour les grands groupes.
- **Le widget intégrable** : exactement le tunnel de réservation, mais
  encapsulé pour être **posé sur le site existant du restaurant** sans en casser
  le style. Fonctionnellement, c'est le même formulaire réutilisé.

### 7.2 Côté restaurant (le back-office)
- **Tableau de bord** : les chiffres du jour (réservations, couverts attendus,
  capacité totale, demandes en attente) et une **prise de réservation rapide**
  pour le téléphone (avec le même anti-surbooking).
- **Plan de salle** : à une **date + heure** choisies, la salle affichée table
  par table, **libre ou occupée** (avec le nom du groupe). C'est la
  visualisation directe du calcul d'occupation — et donc le point où la
  cohérence avec le moteur est cruciale (§4/§6.4).
- **Réservations** : la liste d'un jour, avec les **statuts** modifiables
  (valider une demande, marquer installée, annuler, no-show).
- **Configuration** : les tables et leur capacité (à l'unité ou générées en
  masse), les services et horaires (avec durée de table et **double service**),
  les fermetures, et les réglages généraux (durée, buffer, pas, plafonds…).
- **Charte graphique** : les couleurs de la marque, avec un **aperçu en temps
  réel** du widget.
- **Options** : des interrupteurs pour activer/désactiver les modules payants
  (événements, demandes de groupe, validation, etc.).
- **Notifications** : le journal des messages (e-mails/SMS) qui *seraient*
  envoyés — en démo ils ne partent pas, on les affiche pour montrer le flux.

### 7.3 Le point commun de tous ces écrans
Aucun écran ne « décide » de la disponibilité par lui-même. **Tous interrogent le
même moteur.** Un écran n'est qu'une **fenêtre** sur la logique centrale — jamais
une deuxième implémentation de cette logique.

---

## 8. Conseils pour la reconstruction

### Les 10 conseils à ne pas oublier

1. **Réservez contre des tables réelles, jamais contre un compteur.** C'est tout
   le principe. Un quota se dépasse ; une table occupée, non.
2. **Une seule source de vérité pour « table occupée / libre ».** Une fonction
   (idéalement en base) appelée par le moteur ET par l'affichage. C'est l'erreur
   n°1 que j'ai faite : ne la refaites pas.
3. **Exploitez PostgreSQL à fond.** Modélisez l'occupation en **plages de temps**
   (`tstzrange`) et posez une **contrainte d'exclusion** qui interdit deux
   réservations chevauchantes sur la même table. Vous obtenez un anti-surbooking
   garanti par la base, y compris en cas de réservations simultanées.
4. **Travaillez en dates-heures absolues, pas en minutes depuis minuit.** Ça
   règle d'un coup les services après minuit et les comparaisons de chevauchement.
5. **Fixez le fuseau horaire du restaurant** et raisonnez dedans ; convertissez
   seulement à l'affichage.
6. **Vérifiez ET écrivez dans la même transaction**, avec re-vérification au
   dernier moment (en plus de la contrainte du point 3).
7. **Attribuez la plus petite table qui convient**, et gérez les grands groupes
   par combinaison de tables `combinable`, plafonnée.
8. **Soignez les statuts** : décidez lesquels occupent une table (dont « en
   attente de validation ») et excluez la réservation en cours lors d'une
   modification.
9. **Rendez tout paramétrable par restaurant** (durée, buffer, pas, plafonds,
   double service, horizon) dès le départ — le rétro-adapter est douloureux.
10. **Testez les cas limites en priorité**, pas seulement le cas heureux :
    dernière table en concurrence, groupe trop grand, simple vs double service,
    créneau à cheval sur la fin de service, réservation modifiée.

### L'ordre de construction conseillé

Construisez par **couches**, du cœur vers l'extérieur. Chaque couche doit
fonctionner avant de passer à la suivante.

1. **Le modèle de données** : restaurants, tables (avec capacités et
   `combinable`), services (avec durée de table et double service), fermetures,
   réservations + liaison réservation↔tables. Posez tout de suite la **contrainte
   d'exclusion** anti-chevauchement.
2. **La fonction d'occupation** (le cœur) : « quelles tables sont prises sur
   telle fenêtre ? », avec la règle du double service intégrée. Testez-la seule,
   avec des exemples écrits à la main.
3. **La décision « peut-on asseoir ce groupe ? »** : occupation → tables libres →
   choix de table (plus petite d'abord, puis combinaison) → plafonds de couverts.
4. **La création de réservation** transactionnelle (vérifier + écrire ensemble).
5. **Le calcul des créneaux disponibles** d'une journée (on rejoue la décision
   pour chaque créneau).
6. **Le tunnel de réservation client** (le premier écran, qui consomme les
   créneaux).
7. **Le back-office de configuration** (tables, services, réglages) — sans lui,
   vous testez en dur.
8. **Le plan de salle** (branché sur la **même** fonction d'occupation qu'au
   point 2 — c'est le test ultime de cohérence).
9. **Le reste des écrans** (réservations, statuts, tableau de bord).
10. **Les options et la personnalisation** (événements, demandes de groupe,
    charte graphique…) — utiles mais périphériques.

> Si vous ne deviez retenir qu'**une** phrase : *le moteur, c'est « quelles
> tables sont libres sur cette plage horaire ? » ; écrivez cette réponse une
> seule fois, mettez-la dans la base de données, et faites-en la loi que tous les
> écrans respectent.*
