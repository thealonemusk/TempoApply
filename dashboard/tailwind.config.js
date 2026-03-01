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
        base:    { DEFAULT: '#080c14', surface: '#0d1422', card: '#111827', elevated: '#1a2235' },
        border:  { DEFAULT: 'rgba(255,255,255,0.07)', bright: 'rgba(255,255,255,0.14)' },
        txt:     { primary: '#f0f4ff', secondary: '#8892a4', muted: '#4b5563' },
        accent:  { DEFAULT: '#6366f1', light: '#818cf8', dim: 'rgba(99,102,241,0.2)', 2: '#8b5cf6' },
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
        'card':    '0 4px 24px rgba(0,0,0,0.35)',
        'card-lg': '0 8px 40px rgba(0,0,0,0.5)',
        'glow':    '0 0 24px rgba(99,102,241,0.25)',
        'glow-sm': '0 0 12px rgba(99,102,241,0.2)',
        'gold':    '0 0 20px rgba(245,158,11,0.2)',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'mesh': 'radial-gradient(at 27% 37%, hsla(215,98%,61%,0.06) 0px, transparent 50%), radial-gradient(at 97% 21%, hsla(125,98%,72%,0.04) 0px, transparent 50%), radial-gradient(at 52% 99%, hsla(354,98%,61%,0.04) 0px, transparent 50%)',
        'sidebar-gradient': 'linear-gradient(180deg, #0a0f1e 0%, #080c14 100%)',
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
