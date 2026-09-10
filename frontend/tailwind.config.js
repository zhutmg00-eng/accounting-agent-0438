/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        cyber: {
          bg: '#080C14',
          card: '#0F172A',
          cardHover: '#1E293B',
          border: 'rgba(255, 255, 255, 0.08)',
          accent: '#00F2FE',
          cyan: '#38BDF8',
          blue: '#2563EB',
          purple: '#A855F7',
          crimson: '#EF4444',
          emerald: '#10B981',
          amber: '#F59E0B'
        }
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', '"SF Mono"', 'Menlo', 'monospace'],
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', '"PingFang SC"', '"Microsoft YaHei"', 'sans-serif'],
      },
      animation: {
        'pulse-glow': 'pulseGlow 2.5s infinite',
        'scan': 'scanLine 3s linear infinite',
      },
      keyframes: {
        pulseGlow: {
          '0%, 100%': { opacity: '0.8', filter: 'drop-shadow(0 0 15px rgba(0, 242, 254, 0.4))' },
          '50%': { opacity: '1', filter: 'drop-shadow(0 0 25px rgba(0, 242, 254, 0.8))' },
        },
        scanLine: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(1000%)' },
        }
      }
    },
  },
  plugins: [],
}
