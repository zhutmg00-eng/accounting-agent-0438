/** @type {import('tailwindcss').Config} */

// ---------------------------------------------------------------------------
// AuditMind design tokens — see DESIGN.md for the direction and the reasons.
//
// Two layers live here on purpose while the codebase migrates:
//   * semantic roles (field / paper / ink / fg / seal / risk) — the target
//   * collapsed legacy ramps (slate, cyan, blue, purple, …) — a migration net
//     so existing class names land on-palette instead of on the old navy+neon
//     scheme. Components should migrate to the semantic roles; the ramps only
//     guarantee nothing renders off-palette in the meantime.
// ---------------------------------------------------------------------------

const graphite = {
  50: '#F5F6F7',
  100: '#E7E8EA',
  200: '#C9CBCF',
  300: '#A3A7AE',
  400: '#8A8E95',
  500: '#6E7278',
  600: '#55585E',
  700: '#3F4247',
  800: '#2A2C31',
  900: '#1F2227',
  950: '#17191D'
}

const seal = {
  50: '#FBEDEA',
  100: '#F6D8D2',
  200: '#EBB1A6',
  300: '#E8736A',
  400: '#D05B45',
  500: '#D92B21',
  600: '#B01F18',
  700: '#822616',
  800: '#5E1B10',
  900: '#3D120B',
  950: '#240A06'
}

const riskRed = {
  50: '#FCEDEA',
  100: '#F8D9D3',
  200: '#F0B3A8',
  300: '#E58575',
  400: '#DA5A46',
  500: '#D92B21',
  600: '#B01F18',
  700: '#822616',
  800: '#5C1C12',
  900: '#3A120C',
  950: '#220A06'
}

const ochre = {
  50: '#FBF5E7',
  100: '#F5E9CB',
  200: '#EAD399',
  300: '#DCBA66',
  400: '#D0A845',
  500: '#C9A03F',
  600: '#A67F2C',
  700: '#7E5F20',
  800: '#574116',
  900: '#33260D',
  950: '#1D1508'
}

const moss = {
  50: '#EDF5F0',
  100: '#D7E9DE',
  200: '#AFD3BE',
  300: '#85BA9B',
  400: '#6CA383',
  500: '#5C9070',
  600: '#48755A',
  700: '#365A44',
  800: '#253E2F',
  900: '#16251C',
  950: '#0C140F'
}

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    // Square is the direction. The cap stops any leftover rounded-* class from
    // reintroducing the 12-16px "soft card" default this project is leaving.
    borderRadius: {
      none: '0px',
      sm: '1px',
      DEFAULT: '0px',
      md: '2px',
      lg: '2px',
      xl: '3px',
      '2xl': '4px',
      '3xl': '4px',
      full: '9999px'
    },
    extend: {
      colors: {
        // --- semantic roles (the target) ---
        field: {
          DEFAULT: '#0E0F12', // the room
          sunken: '#0A0B0D',
          raised: '#17191D', // panels, one tone step up - no border needed
          raised2: '#1F2227', // hover / selected / row stripe
          raised3: '#2A2C31' // pressed / active
        },
        paper: {
          DEFAULT: '#EFEFEF', // the lit artifact (library: 'Black and crimson' field)
          deep: '#E2E2E2'
        },
        ink: {
          DEFAULT: '#14151A', // text on paper
          muted: '#5A5C63'
        },
        fg: {
          DEFAULT: '#ECEDEF', // running text on field
          muted: '#A3A7AE',
          faint: '#7D8188'
        },
        seal: {
          DEFAULT: '#D92B21', // the single accent (library: 'Signal red')
          deep: '#B01F18',
          soft: '#E8736A'
        },
        risk: {
          // Text-bearing status red. #D92B21 (the accent) measures only 3.6:1 as
          // small text on the field, so the *word* uses this lighter red at
          // 4.8:1 while `seal` stays the fill and the button. Both still read
          // as the same alarm, and neither fails.
          critical: '#E5544A',
          high: '#D97B4A',
          medium: '#C9A03F',
          clear: '#5C9070'
        },
        surface: {
          panel: '#17191D',
          card: '#1F2227'
        },

        // --- collapsed legacy ramps (migration net) ---
        slate: graphite,
        gray: graphite,
        zinc: graphite,
        neutral: graphite,
        stone: graphite,
        cyan: seal,
        blue: seal,
        sky: seal,
        indigo: seal,
        violet: seal,
        purple: seal,
        fuchsia: seal,
        pink: seal,
        red: riskRed,
        rose: riskRed,
        emerald: moss,
        green: moss,
        teal: moss,
        lime: moss,
        amber: ochre,
        yellow: ochre,
        orange: { ...ochre, 400: '#D97B4A', 500: '#D97B4A' }
      },

      fontFamily: {
        // One voice. IBM Plex Sans sets every Latin letter and every numeral;
        // 中文 comes from the platform's own Chinese face. The split is
        // deliberate: a Simplified-Chinese webfont is megabytes, while
        // PingFang SC / Microsoft YaHei are better hinted for Chinese and
        // already installed. Two families, but only one is ever asked to load.
        sans: [
          '"IBM Plex Sans"',
          'system-ui',
          '-apple-system',
          '"PingFang SC"',
          '"HarmonyOS Sans SC"',
          '"Microsoft YaHei"',
          'sans-serif'
        ],
        // Literal code only: CoT payloads and <pre>/<code> blocks.
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace']
      },

      // Five steps, far apart. Nothing meant to be read sits under 13px.
      fontSize: {
        label: ['13px', { lineHeight: '1.3', letterSpacing: '0.005em' }],
        small: ['14px', { lineHeight: '1.45' }],
        body: ['16px', { lineHeight: '1.5' }],
        title: ['22px', { lineHeight: '1.2', letterSpacing: '-0.01em' }],
        // Fluid by design: the one number a screen is about grows with the room
        // it has, which is how the strongest studied pages size their leading
        // type. The 40px floor keeps it inside a narrow column; the 68px ceiling
        // stops it turning into a poster.
        display: [
          'clamp(40px, 4.6vw, 68px)',
          { lineHeight: '1.04', letterSpacing: '-0.025em' }
        ],
        // legacy names remapped onto the same steps
        xs: ['13px', { lineHeight: '1.3' }],
        sm: ['14px', { lineHeight: '1.45' }],
        base: ['16px', { lineHeight: '1.5' }],
        md: ['16px', { lineHeight: '1.5' }],
        lg: ['18px', { lineHeight: '1.4' }],
        xl: ['22px', { lineHeight: '1.2', letterSpacing: '-0.01em' }],
        '2xl': ['28px', { lineHeight: '1.15', letterSpacing: '-0.015em' }],
        '3xl': ['40px', { lineHeight: '1.05', letterSpacing: '-0.02em' }],
        '4xl': ['40px', { lineHeight: '1.05', letterSpacing: '-0.02em' }],
        '5xl': ['48px', { lineHeight: '1.02', letterSpacing: '-0.02em' }],
        '6xl': ['56px', { lineHeight: '1.0', letterSpacing: '-0.02em' }]
      },

      // Elements at rest carry no shadow. Only real overlays may.
      boxShadow: {
        none: 'none',
        sm: 'none',
        DEFAULT: 'none',
        md: 'none',
        lg: 'none',
        xl: 'none',
        '2xl': 'none',
        inner: 'none',
        overlay: '0 24px 64px -16px rgba(0, 0, 0, 0.72)'
      },

      // Glass was a tell here. Neutralised so a leftover class renders flat.
      backdropBlur: {
        none: '0',
        sm: '0',
        DEFAULT: '0',
        md: '0',
        lg: '0',
        xl: '0',
        '2xl': '0',
        '3xl': '0'
      },
      backdropFilter: { none: 'none' },

      zIndex: {
        base: '0',
        raised: '10',
        sticky: '20',
        drawer: '30',
        overlay: '40',
        modal: '50',
        toast: '60'
      },

      // Numerals align in the text face; monospace is not the tool for that.
      fontVariantNumeric: {
        tabular: 'tabular-nums'
      },

      transitionTimingFunction: {
        out: 'cubic-bezier(0.22, 1, 0.36, 1)',
        inout: 'cubic-bezier(0.65, 0, 0.35, 1)'
      },

      keyframes: {
        // The signature move: an audit stage resolving, and the verdict landing.
        stageIn: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' }
        },
        sweep: {
          '0%': { transform: 'scaleX(0)' },
          '100%': { transform: 'scaleX(1)' }
        },
        settleIn: {
          '0%': { opacity: '0', transform: 'translateY(14px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' }
        }
      },
      animation: {
        'stage-in': 'stageIn 320ms cubic-bezier(0.22, 1, 0.36, 1) both',
        sweep: 'sweep 480ms cubic-bezier(0.22, 1, 0.36, 1) both',
        'settle-in': 'settleIn 420ms cubic-bezier(0.22, 1, 0.36, 1) both'
      }
    }
  },
  plugins: []
}
