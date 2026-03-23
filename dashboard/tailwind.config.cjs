const detecColors = require('../branding/tailwind-colors');

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    screens: {
      sm: '640px',
      md: '768px',
      lg: '1024px',
      xl: '1280px',
      '2xl': '1440px',
    },
    extend: {
      colors: detecColors,
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      boxShadow: {
        'detec-sm': '0 1px 3px rgba(0,0,0,.08)',
        'detec-card': '0 4px 12px rgba(0,0,0,.06)',
      },
      borderRadius: {
        'detec': '10px',
        'detec-md': '12px',
        'detec-lg': '14px',
      },
    },
  },
  plugins: [],
};
