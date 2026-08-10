/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Control-room surfaces
        panel: {
          900: '#0b1017',
          800: '#111823',
          700: '#18212e',
          600: '#222d3d',
        },
        // Risk levels — one source of truth for the whole UI
        risk: {
          low: '#10b981',
          medium: '#f59e0b',
          high: '#f97316',
          critical: '#ef4444',
        },
        accent: '#38bdf8',
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Consolas', 'monospace'],
      },
      animation: {
        'pulse-fast': 'pulse 1.1s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scan': 'scan 2.4s linear infinite',
      },
      keyframes: {
        scan: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(1000%)' },
        },
      },
    },
  },
  plugins: [],
}
