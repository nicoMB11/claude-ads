# Site vitrine Padel App

Site marketing statique de **Padel App** (padelapp.fr). Il est **séparé de l'application**
(qui tourne sur Base44) et **ne se connecte à aucun backend**. Construit avec
[Astro](https://astro.build) + [Tailwind CSS](https://tailwindcss.com), polices
Poppins auto-hébergées, prêt à déployer sur Vercel.

> **L'essentiel à retenir :** tout le texte du site se modifie **sans toucher au code**,
> dans le dossier `src/content/`. Vous n'avez jamais besoin d'ouvrir un fichier `.astro`
> pour changer un titre, un paragraphe ou un item de liste.

---

## 1. Modifier un texte (le cas le plus courant)

Tous les textes vivent dans **`src/content/`**, un fichier par page :

| Page du site | Fichier à modifier |
|---|---|
| Accueil (`/`) | `src/content/pages/accueil.json` |
| Joueurs (`/joueurs`) | `src/content/pages/joueurs.json` |
| Clubs & juges-arbitres (`/clubs`) | `src/content/pages/clubs.json` |
| À propos (`/a-propos`) | `src/content/pages/a-propos.json` |
| Mentions légales (`/mentions-legales`) | `src/content/legal/mentions-legales.md` |
| Confidentialité (`/confidentialite`) | `src/content/legal/confidentialite.md` |
| Menu, pied de page, bandeau | `src/content/global/site.json` |

### Comment faire

1. Ouvrez le fichier `.json` de la page.
2. Repérez la **clé** en français (par ex. `"titre"`, `"sousTitre"`, `"texte"`).
3. Changez **uniquement la valeur** entre guillemets, à droite des deux-points.

```json
"titre": "Le tournoi de padel, enfin à la hauteur du jeu."
          ▲──────────── vous modifiez seulement ce texte ────────────▲
```

### ⚠️ Trois règles d'or

- Ne changez **jamais** la clé (le mot à gauche des deux-points) ni les guillemets `"`.
- Gardez la **virgule** à la fin de chaque ligne, sauf la dernière d'un bloc.
- Pour écrire une apostrophe dans un texte, utilisez `'` normalement — c'est déjà le cas partout.

En cas de doute, comparez avec les lignes voisines : gardez exactement la même ponctuation.

---

## 2. Les pages légales (Mentions légales & Confidentialité)

Elles sont en **Markdown** (`.md`), plus simple à rédiger que le JSON :
`src/content/legal/mentions-legales.md` et `confidentialite.md`.

- Les titres commencent par `##`.
- Le texte s'écrit normalement, en paragraphes.
- Tous les champs à renseigner sont marqués **`[À COMPLÉTER]`**.

> Ces deux textes sont des **modèles de départ à faire valider par un juriste / DPO**
> avant la mise en ligne. Un commentaire en haut de chaque fichier le rappelle.

---

## 3. Ajouter ou retirer un élément dans une liste

Plusieurs sections sont des **listes** (les cartes « trois publics », les étapes du
déroulé, les lignes du tableau avant/après, les blocs clubs, les options du formulaire…).
Le principe est toujours le même : **copier un bloc existant, le coller, puis modifier son
contenu.** C'est aussi de cette manière qu'on ajouterait une question à une éventuelle FAQ.

**Exemple — ajouter une ligne au tableau « avant / après »** (`clubs.json`) :

```json
"lignes": [
  { "avant": "Le tableau se refait sur Excel", "apres": "Généré en un clic, modifiable à la main" },
  { "avant": "VOTRE NOUVELLE LIGNE À GAUCHE",  "apres": "VOTRE NOUVELLE LIGNE À DROITE" }
]
```

Pour **retirer** un élément, supprimez son bloc `{ … }` **et** la virgule qui le sépare
du précédent. Veillez à ne pas laisser de virgule en trop après le dernier élément.

---

## 4. Remplacer une image

Les images se rangent dans **`public/images/`**. Pour remplacer une image :
déposez votre fichier (idéalement en **WebP**, avec des dimensions explicites) dans ce
dossier et indiquez son chemin dans le fichier de contenu correspondant, par ex. :

```json
"photo": "/images/mon-image.webp",
"photoAlt": "Description de l'image pour l'accessibilité et le référencement"
```

Quelques repères :

- **Photos d'équipe / du club pilote** : elles apparaissent aujourd'hui comme des cadres
  « emplacement photo » marqués. Déposez la vraie photo dans `public/images/` puis mettez
  à jour le champ correspondant dans `a-propos.json` / `accueil.json`.
- **Captures d'écran de l'app** (page joueurs) : ce sont pour l'instant des maquettes
  dessinées. Voir la checklist § 8 pour les remplacer par de vraies captures.
- **Logo & favicon** : voir § 5.
- **Images de partage social (Open Graph)** : voir § 6.

Renseignez **toujours** le texte alternatif (`alt`) : c'est important pour
l'accessibilité et le référencement.

---

## 5. Le logo et le favicon

- **Logo affiché sur le site** : `src/components/Logo.astro` (dessiné en SVG aux couleurs
  de la charte : balle verte, trajectoire marine, repère orange).
- **Favicon** (icône de l'onglet) : `public/favicon.svg`.
- **Icône iOS / manifeste** : `public/apple-touch-icon.png`.

> La charte prévoit un **redessin vectoriel définitif** du logo. Quand le fichier SVG
> officiel sera livré, remplacez `public/favicon.svg` et le SVG de `Logo.astro` par la
> version définitive (voir checklist § 8).

---

## 6. Les images de partage social (Open Graph)

Quand on partage une page sur les réseaux, l'image affichée est dans `public/og/`
(une par page). Elles ont été générées aux couleurs de la marque. Pour les régénérer
après un changement de logo ou de titre, un designer peut recréer des images **1200 × 630 px**
et les déposer sous le même nom (`accueil.png`, `joueurs.png`, `clubs.png`, `a-propos.png`).

---

## 7. Le formulaire de démo (et la capture d'e-mail joueur)

Le site n'a **pas de serveur**. Les formulaires envoient les données vers un service
externe que vous configurez, via une variable d'environnement.

1. Créez un formulaire gratuit sur **[Formspree](https://formspree.io)** (ou équivalent)
   et copiez l'URL fournie (elle ressemble à `https://formspree.io/f/xxxxxx`).
2. Créez un fichier `.env` à la racine (copiez `.env.example`) et renseignez :

   ```
   PUBLIC_FORM_ENDPOINT="https://formspree.io/f/xxxxxx"
   ```

3. Sur Vercel, ajoutez la même variable dans **Settings → Environment Variables**.

Tant que cette variable est vide, le formulaire affiche un message d'aide au lieu d'envoyer.
Les messages de succès et d'erreur sont **éditables** dans `clubs.json` → `demo`
(`messageSucces`, `messageErreur`) et `joueurs.json` → `creerCompte`.

---

## 8. Lancer le site sur votre ordinateur

Prérequis : [Node.js](https://nodejs.org) version 18 ou plus.

```bash
npm install        # à faire une seule fois
npm run dev        # lance le site en local sur http://localhost:4321
```

Pour vérifier la version finale avant mise en ligne :

```bash
npm run build      # construit le site
npm run preview    # prévisualise le résultat construit
```

---

## 9. Déployer sur Vercel

1. Poussez le code sur GitHub.
2. Sur [Vercel](https://vercel.com), « New Project » → importez le dépôt.
3. **Important** : réglez le **Root Directory** sur `padel-app` (le site est dans ce
   sous-dossier). Vercel détecte Astro automatiquement (`vercel.json` fournit le reste).
4. Ajoutez les variables d'environnement `PUBLIC_FORM_ENDPOINT` et, si besoin, `SITE_URL`.
5. Déployez. À chaque `git push`, Vercel redéploie tout seul.

---

## 10. Le système de design (pour information)

Toutes les couleurs, typographies et graisses sont **tirées de la charte graphique** :

- **Couleurs** : bleu marine `#061B3A`, orange `#FF6500`, vert padel `#9ED900`,
  blanc `#FFFFFF`, gris clair `#F4F6F8`.
- **Typographie** : Poppins (Regular 400, SemiBold 600, Bold 700), auto-hébergée.
- Définis dans `tailwind.config.mjs` et `src/styles/global.css`.

### Ce qui a été déduit (car la charte ne le précise pas)

Par souci de transparence, voici les choix pris **par cohérence** avec la charte, là où
elle laissait un axe ouvert :

- **Rayons d'angle, ombres et échelle de tailles** : déduits (ombres volontairement très
  discrètes, la charte proscrivant les effets marqués ; échelle de tailles volontairement
  courte, la charte demandant de « limiter le nombre de tailles »).
- **États de survol et composants de formulaire** (champs, menu déroulant, focus clavier) :
  dessinés dans le registre de la marque (accent orange, fond gris clair).
- **Signature visuelle** : « l'arc de trajectoire » (la courbe de la balle en mouvement)
  utilisé **une seule fois** sous le hero comme fil conducteur, et le **repère orange** pour
  ponctuer les étapes clés — directement issus de l'univers graphique de la charte.
- **Logo** : recréé en SVG dans l'esprit de la charte, en attendant le fichier vectoriel
  officiel.

---

## 11. ✅ Checklist — ce qu'il reste à compléter

Ces éléments sont marqués `[À COMPLÉTER]` dans le site. À renseigner avant la mise en ligne :

- [ ] **Textes légaux** : faire valider et compléter `mentions-legales.md` et
      `confidentialite.md` (raison sociale, SIRET, hébergeur, DPO, durées de conservation,
      notamment le traitement du **numéro de licence FFT**).
- [ ] **Citation du club pilote** : remplacer le texte, l'auteur, le rôle et la photo dans
      `accueil.json` → `preuve.citation`.
- [ ] **Chiffre de gain de temps** : renseigner `accueil.json` → `preuve.chiffre.valeur`
      (par ex. `"3 h"`).
- [ ] **Photos de l'équipe** : `a-propos.json` → `equipe.membres` (+ dépôt des fichiers).
- [ ] **Photos du récit** (page à propos) : `a-propos.json` → `recit[].image`.
- [ ] **Captures d'écran de l'app** (page joueurs) : remplacer les maquettes dessinées par
      de vraies captures (voir `src/components/Mockup.astro`).
- [ ] **Endpoint du formulaire** : configurer `PUBLIC_FORM_ENDPOINT` (§ 7).
- [ ] **Logo vectoriel officiel** : remplacer le SVG provisoire quand la charte est
      finalisée (§ 5).
- [ ] **Liens App Store / Google Play** : à ajouter dans `joueurs.json` → `creerCompte`
      quand l'application est publiée.

> Aucun chiffre ni témoignage n'a été inventé : tous les emplacements de preuve portent
> un marqueur `[À COMPLÉTER]` visible.
