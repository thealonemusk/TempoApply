/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        serif: ['"Playfair Display"', '"Times New Roman"', 'Georgia', 'serif'],
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        ink: {
          DEFAULT: '#1a1209',
          light: '#2d2415',
          muted: '#5c4d3a',
        },
        newsprint: {
          DEFAULT: '#f5f0e8',
          dark: '#e8e0d0',
          darker: '#d9cebc',
        },
        accent: {
          gold: '#b8860b',
          'gold-light': '#d4a017',
          red: '#8b1a1a',
          blue: '#1a3a5c',
        },
        platform: {
          linkedin: '#0077B5',
          indeed: '#003A9B',
          naukri: '#ff7555',
          instahyre: '#6c63ff',
          manual: '#5c4d3a',
        },
        score: {
          high: '#2d6a2d',
          mid: '#8b6914',
          low: '#8b1a1a',
        },
      },
      backgroundImage: {
        'newsprint-texture': "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='4' height='4'%3E%3Crect width='4' height='4' fill='%23f5f0e8'/%3E%3Ccircle cx='1' cy='1' r='0.5' fill='%23d9cebc' opacity='0.4'/%3E%3C/svg%3E\")",
      },
      boxShadow: {
        'newspaper': '2px 2px 0px rgba(26, 18, 9, 0.15)',
        'newspaper-lg': '4px 4px 0px rgba(26, 18, 9, 0.15)',
      },
    },
  },
  plugins: [],
};
