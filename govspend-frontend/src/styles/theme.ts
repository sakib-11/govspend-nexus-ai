import { createTheme, ThemeOptions } from '@mui/material/styles';

export const pastelPalette = {
  primary: {
    main: '#5B7C99',
    light: '#D9E7F4',
    dark: '#2E455C',
    contrastText: '#FFFFFF',
  },
  secondary: {
    main: '#A98FB6',
    light: '#EADFF5',
    dark: '#6A5670',
    contrastText: '#FFFFFF',
  },
  success: {
    main: '#5C9C82',
    light: '#D9F0E5',
    dark: '#2D5E4C',
    contrastText: '#FFFFFF',
  },
  warning: {
    main: '#C78F4A',
    light: '#F6E8CB',
    dark: '#83591A',
    contrastText: '#FFFFFF',
  },
  error: {
    main: '#C76F6F',
    light: '#F9E0E0',
    dark: '#7A3E3E',
    contrastText: '#FFFFFF',
  },
  info: {
    main: '#6D8CC9',
    light: '#E3ECFB',
    dark: '#355999',
    contrastText: '#FFFFFF',
  },
  background: {
    default: '#F7FAFC',
    paper: '#FFFFFF',
  },
  text: {
    primary: '#1F2A37',
    secondary: '#5E6D7D',
  },
  divider: '#E8EDF3',
};

export const glassTokens = {
  light: {
    primary: {
      bg: 'rgba(91, 124, 153, 0.08)',
      border: 'rgba(91, 124, 153, 0.18)',
      shadow: 'rgba(91, 124, 153, 0.12)',
    },
    surface: {
      bg: 'rgba(255, 255, 255, 0.72)',
      border: 'rgba(255, 255, 255, 0.28)',
      shadow: 'rgba(15, 23, 42, 0.06)',
      innerGlow: 'rgba(255, 255, 255, 0.7)',
    },
    overlay: {
      bg: 'rgba(248, 250, 252, 0.88)',
      border: 'rgba(148, 163, 184, 0.18)',
      shadow: 'rgba(15, 23, 42, 0.05)',
    },
    input: {
      bg: 'rgba(255, 255, 255, 0.9)',
      border: 'rgba(148, 163, 184, 0.22)',
      focusBorder: 'rgba(91, 124, 153, 0.5)',
      focusRing: 'rgba(186, 219, 254, 0.35)',
    },
  },
  dark: {
    primary: {
      bg: 'rgba(156, 183, 208, 0.1)',
      border: 'rgba(156, 183, 208, 0.15)',
      shadow: 'rgba(156, 183, 208, 0.08)',
    },
    surface: {
      bg: 'rgba(22, 34, 51, 0.82)',
      border: 'rgba(156, 183, 208, 0.12)',
      shadow: 'rgba(0, 0, 0, 0.25)',
      innerGlow: 'rgba(255, 255, 255, 0.03)',
    },
    overlay: {
      bg: 'rgba(16, 27, 42, 0.88)',
      border: 'rgba(156, 183, 208, 0.1)',
      shadow: 'rgba(0, 0, 0, 0.2)',
    },
    input: {
      bg: 'rgba(22, 34, 51, 0.9)',
      border: 'rgba(148, 163, 184, 0.18)',
      focusBorder: 'rgba(156, 183, 208, 0.4)',
      focusRing: 'rgba(156, 183, 208, 0.15)',
    },
  },
};

export const depthShadow = {
  xs: '0 2px 8px rgba(15, 23, 42, 0.04)',
  sm: '0 6px 16px rgba(15, 23, 42, 0.06)',
  md: '0 12px 28px rgba(15, 23, 42, 0.08)',
  lg: '0 20px 48px rgba(15, 23, 42, 0.10)',
  xl: '0 28px 64px rgba(15, 23, 42, 0.14)',
  inset: 'inset 0 1px 0 rgba(255, 255, 255, 0.7)',
  glow: {
    primary: '0 0 24px rgba(91, 124, 153, 0.18)',
    secondary: '0 0 24px rgba(169, 143, 182, 0.18)',
    success: '0 0 24px rgba(92, 156, 130, 0.16)',
    warning: '0 0 24px rgba(199, 143, 74, 0.16)',
    error: '0 0 24px rgba(199, 111, 111, 0.16)',
  },
};

export const gradientTokens = {
  primary: 'linear-gradient(135deg, #B7CFE7 0%, #9DB8D1 100%)',
  primaryHover: 'linear-gradient(135deg, #A7C0DB 0%, #86A7C4 100%)',
  secondary: 'linear-gradient(135deg, #E9D9F3 0%, #D7C4E1 100%)',
  secondaryHover: 'linear-gradient(135deg, #E1C8ED 0%, #C8AFD8 100%)',
  success: 'linear-gradient(135deg, #D2F0D9 0%, #B7E1C6 100%)',
  successHover: 'linear-gradient(135deg, #C6EBD0 0%, #A5D3B2 100%)',
  warning: 'linear-gradient(135deg, #F6E8CB 0%, #EFD9A3 100%)',
  warningHover: 'linear-gradient(135deg, #EFDFAE 0%, #E5CF92 100%)',
  error: 'linear-gradient(135deg, #F7D7D7 0%, #EFC0C0 100%)',
  errorHover: 'linear-gradient(135deg, #F4CECE 0%, #E7B0B0 100%)',
  surface: 'linear-gradient(180deg, #FFFFFF 0%, #F9FBFF 100%)',
  surfaceDark: 'linear-gradient(180deg, rgba(248,251,255,0.96) 0%, rgba(244,248,252,0.93) 100%)',
  ambientBlue: 'radial-gradient(circle at top left, rgba(186, 214, 255, 0.24), transparent 30%)',
  ambientLavender: 'radial-gradient(circle at bottom right, rgba(216, 180, 254, 0.18), transparent 28%)',
  ambientSunset: 'radial-gradient(circle at 70% 80%, rgba(253, 224, 71, 0.12), transparent 20%)',
};

export const motionTokens = {
  duration: {
    instant: '80ms',
    fast: '160ms',
    normal: '260ms',
    slow: '420ms',
    slower: '600ms',
  },
  easing: {
    easeOut: 'cubic-bezier(0.16, 1, 0.3, 1)',
    easeInOut: 'cubic-bezier(0.65, 0, 0.35, 1)',
    bounce: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
    smooth: 'cubic-bezier(0.22, 1, 0.36, 1)',
  },
};

const getDesignTokens = (mode: 'light' | 'dark'): ThemeOptions => ({
  palette: {
    mode,
    ...(mode === 'light'
      ? pastelPalette
      : {
          primary: {
            main: '#9CB7D0',
            light: '#DDEAF7',
            dark: '#5B7C99',
            contrastText: '#18212D',
          },
          secondary: {
            main: '#C5A9CD',
            light: '#F1E4F8',
            dark: '#8D759A',
            contrastText: '#18212D',
          },
          background: {
            default: '#0F172A',
            paper: '#162233',
          },
          text: {
            primary: '#EAF1FF',
            secondary: '#AAB9CD',
          },
          error: {
            main: '#F0B7B7',
            light: '#FCE9E9',
            dark: '#C76F6F',
          },
          warning: {
            main: '#F1C983',
            light: '#F9EAC2',
            dark: '#C78F4A',
          },
          success: {
            main: '#A9D7BF',
            light: '#DFF3E7',
            dark: '#5C9C82',
          },
          info: {
            main: '#B9CFF5',
            light: '#E4EEFF',
            dark: '#6D8CC9',
          },
          divider: '#243244',
        }),
  },
  typography: {
    fontFamily: '"Inter", "Roboto", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    h1: { fontWeight: 900, letterSpacing: '-0.06em', lineHeight: 1.15, fontSize: 'clamp(2rem, 4vw, 3rem)' },
    h2: { fontWeight: 800, letterSpacing: '-0.04em', lineHeight: 1.2, fontSize: 'clamp(1.75rem, 3.5vw, 2.5rem)' },
    h3: { fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1.25 },
    h4: { fontWeight: 700, letterSpacing: '-0.02em', lineHeight: 1.3, color: mode === 'light' ? '#1F2A37' : '#EAF1FF' },
    h5: { fontWeight: 700, letterSpacing: '-0.01em', lineHeight: 1.35 },
    h6: { fontWeight: 700, lineHeight: 1.4 },
    subtitle1: { fontWeight: 700, lineHeight: 1.5 },
    subtitle2: { fontWeight: 600, lineHeight: 1.5 },
    body1: { lineHeight: 1.6, fontSize: '1rem' },
    body2: { lineHeight: 1.55, fontSize: '0.875rem' },
    button: { textTransform: 'none', fontWeight: 700, letterSpacing: '0.01em', lineHeight: 1.4 },
    caption: { lineHeight: 1.4, letterSpacing: '0.01em' },
    overline: { fontWeight: 700, letterSpacing: '0.14em', lineHeight: 1.5 },
  },
  shape: { borderRadius: 18 },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 14,
          boxShadow: 'none',
          padding: '10px 20px',
          fontWeight: 700,
          letterSpacing: '0.01em',
          transition: `all ${motionTokens.duration.normal} ${motionTokens.easing.easeOut}`,
          position: 'relative',
          overflow: 'hidden',
          '&::after': {
            content: '""',
            position: 'absolute',
            inset: 0,
            background: mode === 'light'
              ? 'linear-gradient(135deg, rgba(255,255,255,0.25) 0%, transparent 60%)'
              : 'linear-gradient(135deg, rgba(255,255,255,0.08) 0%, transparent 60%)',
            borderRadius: 'inherit',
            pointerEvents: 'none',
          },
          '&:hover': {
            boxShadow: depthShadow.glow.primary,
            transform: 'translateY(-2px)',
          },
          '&:active': {
            transform: 'translateY(0)',
            boxShadow: depthShadow.xs,
          },
        },
        contained: {
          boxShadow: depthShadow.sm,
        },
        outlined: {
          borderWidth: '1.5px',
          '&:hover': {
            borderWidth: '1.5px',
            boxShadow: depthShadow.glow.primary,
            transform: 'translateY(-2px)',
          },
        },
      },
      defaultProps: {
        disableElevation: true,
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          boxShadow: depthShadow.md,
          border: mode === 'light'
            ? '1px solid rgba(148, 163, 184, 0.14)'
            : '1px solid rgba(148, 163, 184, 0.12)',
          borderRadius: 20,
          background: mode === 'light'
            ? gradientTokens.surface
            : 'rgba(22, 34, 51, 0.88)',
          transition: `box-shadow ${motionTokens.duration.normal} ${motionTokens.easing.easeOut}`,
          '&:hover': {
            boxShadow: depthShadow.lg,
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 22,
          backgroundColor: mode === 'light' ? '#FFFFFF' : '#162233',
          border: mode === 'light'
            ? '1px solid rgba(148, 163, 184, 0.14)'
            : '1px solid rgba(148, 163, 184, 0.12)',
          boxShadow: `${depthShadow.md}, ${depthShadow.inset}`,
          transition: `all ${motionTokens.duration.normal} ${motionTokens.easing.easeOut}`,
          background: mode === 'light'
            ? gradientTokens.surface
            : 'linear-gradient(180deg, rgba(22,34,51,0.96) 0%, rgba(18,28,40,0.92) 100%)',
          '&:hover': {
            transform: 'translateY(-4px)',
            boxShadow: `${depthShadow.xl}, ${depthShadow.inset}`,
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          fontWeight: 700,
          backgroundColor: mode === 'light' ? '#F8FAFC' : '#1B2637',
          color: mode === 'light' ? '#5E6D7D' : '#C8D7EA',
          fontSize: '0.76rem',
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          borderBottom: mode === 'light'
            ? '1px solid rgba(148, 163, 184, 0.12)'
            : '1px solid rgba(148, 163, 184, 0.1)',
        },
        body: {
          borderBottom: mode === 'light' ? '1px solid #EDF2F7' : '1px solid #243244',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 700,
          borderRadius: 999,
          letterSpacing: '0.02em',
          border: mode === 'light'
            ? '1px solid rgba(148, 163, 184, 0.2)'
            : '1px solid rgba(148, 163, 184, 0.15)',
          transition: `all ${motionTokens.duration.fast} ${motionTokens.easing.easeOut}`,
          '&:hover': {
            transform: 'translateY(-1px)',
            boxShadow: depthShadow.sm,
          },
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          boxShadow: 'none',
          borderBottom: mode === 'light'
            ? '1px solid rgba(148, 163, 184, 0.14)'
            : '1px solid rgba(148, 163, 184, 0.1)',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          background: mode === 'light'
            ? 'linear-gradient(180deg, rgba(248,251,255,0.96) 0%, rgba(244,248,252,0.93) 100%)'
            : 'linear-gradient(180deg, rgba(16,27,42,0.96) 0%, rgba(12,21,32,0.92) 100%)',
          borderRight: mode === 'light'
            ? '1px solid rgba(148, 163, 184, 0.18)'
            : '1px solid rgba(148, 163, 184, 0.12)',
          boxShadow: '8px 0 24px rgba(15, 23, 42, 0.04)',
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: 24,
          background: mode === 'light'
            ? 'rgba(255,255,255,0.92)'
            : 'rgba(22, 34, 51, 0.94)',
          backdropFilter: 'blur(24px)',
          border: mode === 'light'
            ? '1px solid rgba(255,255,255,0.3)'
            : '1px solid rgba(148, 163, 184, 0.12)',
          boxShadow: `${depthShadow.xl}, 0 0 0 1px ${mode === 'light' ? 'rgba(148,163,184,0.06)' : 'rgba(0,0,0,0.2)'}`,
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          transition: `all ${motionTokens.duration.fast} ${motionTokens.easing.easeOut}`,
          '&:hover': {
            transform: 'scale(1.06)',
            boxShadow: depthShadow.sm,
          },
        },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          borderRadius: 10,
          background: mode === 'light' ? '#1F2A37' : '#EAF1FF',
          color: mode === 'light' ? '#FFFFFF' : '#1F2A37',
          boxShadow: depthShadow.md,
          fontSize: '0.8rem',
          fontWeight: 600,
          padding: '6px 12px',
        },
        arrow: {
          color: mode === 'light' ? '#1F2A37' : '#EAF1FF',
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 14,
            background: mode === 'light'
              ? 'rgba(255, 255, 255, 0.9)'
              : 'rgba(22, 34, 51, 0.9)',
            transition: `all ${motionTokens.duration.normal} ${motionTokens.easing.easeOut}`,
            '&:hover': {
              boxShadow: depthShadow.xs,
            },
            '&.Mui-focused': {
              boxShadow: `0 0 0 4px ${glassTokens.light.input.focusRing}`,
            },
          },
        },
      },
    },
    MuiMenu: {
      styleOverrides: {
        paper: {
          borderRadius: 16,
          background: mode === 'light'
            ? 'rgba(255, 255, 255, 0.96)'
            : 'rgba(22, 34, 51, 0.96)',
          backdropFilter: 'blur(20px)',
          border: mode === 'light'
            ? '1px solid rgba(148, 163, 184, 0.14)'
            : '1px solid rgba(148, 163, 184, 0.1)',
          boxShadow: `${depthShadow.lg}, ${depthShadow.inset}`,
          marginTop: 4,
        },
        list: {
          padding: '6px',
        },
      },
    },
    MuiMenuItem: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          margin: '2px 0',
          padding: '8px 12px',
          transition: `all ${motionTokens.duration.fast} ${motionTokens.easing.easeOut}`,
          '&:hover': {
            background: mode === 'light'
              ? 'rgba(91, 124, 153, 0.06)'
              : 'rgba(156, 183, 208, 0.08)',
          },
        },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: {
          borderRadius: 999,
          height: 6,
          background: mode === 'light'
            ? 'rgba(148, 163, 184, 0.12)'
            : 'rgba(148, 163, 184, 0.1)',
        },
        bar: {
          borderRadius: 999,
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 14,
          backdropFilter: 'blur(8px)',
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          margin: '2px 4px',
          transition: `all ${motionTokens.duration.fast} ${motionTokens.easing.easeOut}`,
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          transition: `all ${motionTokens.duration.fast} ${motionTokens.easing.easeOut}`,
        },
      },
    },
    MuiBadge: {
      styleOverrides: {
        badge: {
          boxShadow: depthShadow.xs,
          border: `2px solid ${mode === 'light' ? '#FFFFFF' : '#162233'}`,
        },
      },
    },
  },
});

export const getTheme = (mode: 'light' | 'dark') => createTheme(getDesignTokens(mode));
export const theme = getTheme('light');
