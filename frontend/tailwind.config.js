/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        root: '#0b1120',
        surface: '#111827',
        elevated: '#1e293b',
        border: '#1e293b',
        accent: {
          DEFAULT: '#3b82f6',
          light: '#60a5fa',
          bg: 'rgba(59,130,246,0.1)',
        },
        text: {
          primary: '#f1f5f9',
          secondary: '#94a3b8',
          muted: '#64748b',
        },
        green: { DEFAULT: '#22c55e', bg: 'rgba(34,197,94,0.1)' },
        yellow: { DEFAULT: '#eab308', bg: 'rgba(234,179,8,0.1)' },
        red: { DEFAULT: '#ef4444', bg: 'rgba(239,68,68,0.1)' },
        purple: { DEFAULT: '#a855f7', bg: 'rgba(168,85,247,0.1)' },
        teal: { DEFAULT: '#14b8a6' },
        orange: { DEFAULT: '#f97316' },
        pink: { DEFAULT: '#ec4899' },
      },
      borderRadius: {
        card: '10px',
        btn: '20px',
      },
    },
  },
  plugins: [],
}
