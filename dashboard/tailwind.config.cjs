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
        sans:  ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        mono:  ['"IBM Plex Mono"', 'monospace'],
        data:  ['"IBM Plex Mono"', 'monospace'],   // alias for data display
      },
      spacing: {
        // 4px base grid (supplements Tailwind defaults)
        '0.5': '2px',
        '1':   '4px',
        '1.5': '6px',
        '2':   '8px',
        '2.5': '10px',
        '3':   '12px',
        '3.5': '14px',
        '4':   '16px',
        '5':   '20px',
        '6':   '24px',
        '7':   '28px',
        '8':   '32px',
        '10':  '40px',
        '12':  '48px',
        '14':  '56px',    // icon rail width
        '16':  '64px',
      },
      borderRadius: {
        'detec':    '2px',    // sharp — buttons, inputs, badges
        'detec-md': '4px',    // cards, panels
        'detec-lg': '6px',    // modals, dropdowns
      },
      fontSize: {
        'data-xs': ['10px', { lineHeight: '16px', letterSpacing: '0.02em' }],
        'data-sm': ['11px', { lineHeight: '16px', letterSpacing: '0.01em' }],
        'data':    ['12px', { lineHeight: '18px', letterSpacing: '0em' }],
        'data-lg': ['13px', { lineHeight: '20px', letterSpacing: '0em' }],
      },
      // No box shadows — borders-only depth strategy
    },
  },
  plugins: [],
};
