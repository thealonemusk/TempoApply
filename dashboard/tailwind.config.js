/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans:    ['"Inter"', 'system-ui', 'sans-serif'],
        display: ['"Plus Jakarta Sans"', '"Inter"', 'system-ui', 'sans-serif'],
        mono:    ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        base:    { DEFAULT: '#f1f2f4', surface: '#f8f9fa', card: '#ffffff', elevated: '#ffffff' },
        border:  { DEFAULT: '#e5e7eb', bright: '#d1d5db' },
        txt:     { primary: '#111827', secondary: '#4b5563', muted: '#9ca3af' },
        accent:  { DEFAULT: '#0d7f6c', light: '#14b8a6', dim: 'rgba(13,127,108,0.1)', 2: '#0f9681' },
        gold:    { DEFAULT: '#f59e0b', light: '#fbbf24', dim: 'rgba(245,158,11,0.15)' },
        emerald: { DEFAULT: '#10b981', dim: 'rgba(16,185,129,0.15)' },
        danger:  { DEFAULT: '#ef4444', dim: 'rgba(239,68,68,0.12)' },
        platform: {
          linkedin: '#60a5fa',
          indeed:   '#818cf8',
          naukri:   '#fb923c',
          instahyre:'#a78bfa',
          manual:   '#94a3b8',
        },
      },
      boxShadow: {
        'card':    '0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.03)',
        'card-lg': '0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03)',
        'glow':    '0 1px 3px rgba(0,0,0,0.05)',
        'glow-sm': '0 1px 2px rgba(0,0,0,0.02)',
        'gold':    '0 1px 3px rgba(245,158,11,0.1)',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
      },
      animation: {
        'fade-in-up': 'fadeInUp 0.35s cubic-bezier(.16,1,.3,1) forwards',
        'fade-in':    'fadeIn 0.25s ease forwards',
        'spin-slow':  'spin-slow 1.5s linear infinite',
        'pulse-ring': 'pulse-ring 2s ease-out infinite',
      },
    },
  },
  plugins: [],
};
