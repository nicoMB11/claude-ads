import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import sitemap from '@astrojs/sitemap';

// URL de production du site. Sert au sitemap, aux balises canoniques et Open Graph.
// À adapter le jour du déploiement (ou via la variable d'environnement SITE_URL sur Vercel).
const SITE_URL = process.env.SITE_URL || 'https://padelapp.fr';

// https://astro.build
export default defineConfig({
  site: SITE_URL,
  integrations: [
    tailwind({ applyBaseStyles: false }),
    sitemap(),
  ],
  build: {
    inlineStylesheets: 'auto',
  },
  compressHTML: true,
});
