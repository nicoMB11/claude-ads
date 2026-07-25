import { defineCollection, z } from 'astro:content';

/**
 * Déclaration des collections de contenu.
 *
 * TOUT le texte du site vit ici, dans src/content/. Les composants ne
 * contiennent aucune phrase en dur : ils lisent ces fichiers.
 *
 * Pour modifier un texte : ouvrez le fichier .json (ou .md pour les pages
 * légales) et changez la VALEUR, jamais la clé ni les guillemets.
 * Voir le README à la racine pour le guide complet.
 *
 * Les schémas ci-dessous sont volontairement souples (beaucoup de champs
 * optionnels) pour qu'une petite faute de frappe ne bloque jamais le site.
 */

// Un bouton / lien réutilisable.
const lien = z.object({
  libelle: z.string(),
  href: z.string(),
  style: z.enum(['principal', 'secondaire', 'lien']).optional(),
});

// Réglages globaux : navigation, pied de page, bandeau.
const global = defineCollection({
  type: 'data',
  schema: z.object({
    nom: z.string(),
    domaine: z.string(),
    baseline: z.string(),
    nav: z.array(lien),
    navCta: lien.optional(),
    bandeauPilote: z.string().optional(),
    footer: z.object({
      tagline: z.string(),
      colonnes: z
        .array(
          z.object({
            titre: z.string(),
            liens: z.array(lien),
          }),
        )
        .optional(),
      legal: z.array(lien).optional(),
      copyright: z.string(),
      mentionSepare: z.string().optional(),
    }),
  }),
});

// Pages éditoriales (accueil, joueurs, clubs, à-propos).
// Schéma très permissif : chaque page a sa propre structure de sections.
const pages = defineCollection({
  type: 'data',
  schema: z
    .object({
      meta: z.object({
        titre: z.string(),
        description: z.string(),
        ogImage: z.string().optional(),
      }),
    })
    .passthrough(),
});

// Pages légales en Markdown (texte long, modèles à faire valider).
const legal = defineCollection({
  type: 'content',
  schema: z.object({
    titre: z.string(),
    description: z.string(),
    miseAJour: z.string().optional(),
  }),
});

export const collections = { global, pages, legal };
