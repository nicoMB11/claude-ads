/**
 * Configuration Tailwind — dérivée intégralement de la charte graphique Padel App.
 * Les valeurs de couleur, de typographie et de graisses sont celles du PDF (pages 04 et 06).
 * Les échelles de rayons, d'ombres et d'espacement sont déduites par cohérence (voir README).
 *
 * NE PAS ajouter ici de dégradés, d'accents ou d'effets absents de la charte.
 */
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,ts,tsx,md,mdx}'],
  theme: {
    // Palette stricte de la charte — pas de couleur hors marque.
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      marine: {
        DEFAULT: '#061B3A', // Bleu marine — couleur principale (55–65 %)
        900: '#03102A',
        800: '#061B3A',
        700: '#0C2A55',
        600: '#143A70',
      },
      orange: {
        DEFAULT: '#FF6500', // Orange — action & conversion (8–12 %)
        600: '#E65B00',
        700: '#CC5100',
      },
      vert: {
        DEFAULT: '#9ED900', // Vert padel — accent sportif (5–10 %)
        600: '#7FAF00',
      },
      blanc: '#FFFFFF',
      gris: {
        DEFAULT: '#F4F6F8', // Gris clair — fonds secondaires
        200: '#E4E9EE',
        400: '#9AA6B2', // gris de texte secondaire (déduit, AA sur blanc)
        600: '#5A6B7B',
      },
    },
    fontFamily: {
      // Poppins auto-hébergée + repli système imposé par la charte.
      sans: ['Poppins', 'Arial', 'system-ui', 'sans-serif'],
    },
    // Échelle typographique volontairement courte (règle charte : « limiter les tailles »).
    fontSize: {
      xs: ['0.875rem', { lineHeight: '1.5' }], // 14
      sm: ['1rem', { lineHeight: '1.6' }], // 16
      base: ['1.125rem', { lineHeight: '1.65' }], // 18
      lg: ['1.25rem', { lineHeight: '1.5' }], // 20
      xl: ['1.5rem', { lineHeight: '1.35' }], // 24
      '2xl': ['2rem', { lineHeight: '1.2' }], // 32
      '3xl': ['2.75rem', { lineHeight: '1.1' }], // 44
      '4xl': ['3.75rem', { lineHeight: '1.05' }], // 60
    },
    extend: {
      fontWeight: {
        normal: '400', // Poppins Regular — corps
        semibold: '600', // Poppins SemiBold — sous-titres, boutons
        bold: '700', // Poppins Bold — titres, accroches
      },
      borderRadius: {
        sm: '6px',
        DEFAULT: '10px',
        lg: '16px',
        xl: '24px',
        '2xl': '32px',
      },
      // Ombres très douces uniquement — la charte proscrit les effets marqués.
      boxShadow: {
        soft: '0 1px 2px rgba(6, 27, 58, 0.04), 0 8px 24px rgba(6, 27, 58, 0.06)',
        card: '0 1px 3px rgba(6, 27, 58, 0.06), 0 12px 32px rgba(6, 27, 58, 0.08)',
        none: 'none',
      },
      maxWidth: {
        prose: '68ch',
        container: '1200px',
      },
      transitionTimingFunction: {
        'out-soft': 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
    },
  },
  plugins: [],
};
