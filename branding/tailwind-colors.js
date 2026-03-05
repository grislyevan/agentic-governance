/**
 * Detec — Tailwind CSS Color Tokens
 *
 * Usage: spread into your tailwind.config.js theme.extend.colors
 *
 * Example:
 *   const detecColors = require('./branding/tailwind-colors');
 *   module.exports = {
 *     theme: { extend: { colors: detecColors } }
 *   };
 */

module.exports = {
  detec: {
    primary: {
      50:  '#eef2ff',
      100: '#e0e7ff',
      200: '#c7d2fe',
      300: '#a5b4fc',
      400: '#818cf8',
      500: '#6366f1',
      600: '#4f46e5',
      700: '#4338ca',
      800: '#3730a3',
      900: '#312e81',
      950: '#1e1b4b',
      DEFAULT: '#6366f1',
    },
    teal: {
      50:  '#f0fdfa',
      100: '#ccfbf1',
      200: '#99f6e4',
      300: '#5eead4',
      400: '#2dd4bf',
      500: '#14b8a6',
      600: '#0d9488',
      700: '#0f766e',
      800: '#115e59',
      900: '#134e4a',
      950: '#042f2e',
      DEFAULT: '#14b8a6',
    },
    amber: {
      50:  '#fffbeb',
      100: '#fef3c7',
      200: '#fde68a',
      300: '#fcd34d',
      400: '#fbbf24',
      500: '#f59e0b',
      600: '#d97706',
      700: '#b45309',
      800: '#92400e',
      900: '#78350f',
      950: '#451a03',
      DEFAULT: '#f59e0b',
    },
    slate: {
      50:  '#f8fafc',
      100: '#f1f5f9',
      200: '#e2e8f0',
      300: '#cbd5e1',
      400: '#94a3b8',
      500: '#64748b',
      600: '#475569',
      700: '#334155',
      800: '#1e293b',
      900: '#0f172a',
      950: '#020617',
    },
    enforce: {
      detect:   '#6366f1',
      warn:     '#f59e0b',
      approval: '#f97316',
      block:    '#ef4444',
    },
    confidence: {
      high:   '#14b8a6',
      medium: '#f59e0b',
      low:    '#94a3b8',
    },
  },
};
