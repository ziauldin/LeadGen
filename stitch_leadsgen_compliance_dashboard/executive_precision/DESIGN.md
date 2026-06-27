---
name: Executive Precision
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#464555'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#777587'
  outline-variant: '#c7c4d8'
  surface-tint: '#4d44e3'
  primary: '#3525cd'
  on-primary: '#ffffff'
  primary-container: '#4f46e5'
  on-primary-container: '#dad7ff'
  inverse-primary: '#c3c0ff'
  secondary: '#006c49'
  on-secondary: '#ffffff'
  secondary-container: '#6cf8bb'
  on-secondary-container: '#00714d'
  tertiary: '#684000'
  on-tertiary: '#ffffff'
  tertiary-container: '#885500'
  on-tertiary-container: '#ffd4a4'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e2dfff'
  primary-fixed-dim: '#c3c0ff'
  on-primary-fixed: '#0f0069'
  on-primary-fixed-variant: '#3323cc'
  secondary-fixed: '#6ffbbe'
  secondary-fixed-dim: '#4edea3'
  on-secondary-fixed: '#002113'
  on-secondary-fixed-variant: '#005236'
  tertiary-fixed: '#ffddb8'
  tertiary-fixed-dim: '#ffb95f'
  on-tertiary-fixed: '#2a1700'
  on-tertiary-fixed-variant: '#653e00'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display:
    fontFamily: Inter
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  sidebar-width: 260px
  container-max: 1440px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 32px
---

## Brand & Style
The design system is engineered for high-stakes B2B lead intelligence, where compliance and data clarity are paramount. The brand personality is **authoritative, surgical, and transparent**. It avoids the "bubbly" aesthetics of consumer apps in favor of a refined, high-density interface that mirrors the precision of the data it serves.

The aesthetic follows a **Corporate / Modern** movement, drawing inspiration from high-end productivity tools. It utilizes a "density-first" philosophy—maximizing information visibility through rigorous alignment and subtle depth rather than heavy ornamentation. The emotional goal is to evoke a sense of total control and unwavering reliability for the professional user.

## Colors
This design system utilizes a sophisticated palette centered around **Deep Indigo** to represent trust and intelligence. 

- **Primary (#4F46E5):** Reserved for brand moments and the most critical call-to-action.
- **Success/Compliant (#10B981):** Used for verified data points and positive status indicators.
- **Warning/Review (#F59E0B):** Signals items requiring human intervention or compliance checks.
- **Danger/Blocked (#F43F5E):** Identifies opt-outs, blacklisted domains, or critical errors.
- **Neutrals:** A comprehensive Slate scale provides the structural framework. Slate-50 is the primary canvas, Slate-200 provides borders, and Slate-900 is used for maximum-contrast text.

## Typography
The system relies exclusively on **Inter**, a typeface optimized for screen legibility and data-heavy environments. 

Headings are compact with slight negative letter-spacing to appear "locked-in" and professional. For data-dense views (tables/lists), use `body-md` and `label-md` to ensure high information visibility without sacrificing scanning speed. The `label-sm` role is specifically designed for technical metadata and secondary status tags, using a semi-bold uppercase style to differentiate it from interactive text.

## Layout & Spacing
The layout follows a **structured fixed-fluid hybrid**. A persistent left sidebar (260px) serves as the primary navigation anchor, utilizing a Slate-900 or Slate-50 background to create a distinct functional zone. 

The main content area uses a 12-column grid. For complex data management, elements should be grouped into cards that span logical column counts (e.g., 4-column filters, 8-column data tables). 

**Responsive Behavior:**
- **Desktop:** 32px margins, 24px gutters.
- **Tablet:** 24px margins, sidebar collapses into a hamburger menu or narrow icon-rail.
- **Mobile:** 16px margins, vertical stack for all card-based components.

## Elevation & Depth
This design system uses a **Tonal Layering** approach combined with **Ambient Shadows**. 

Depth is communicated through three primary tiers:
1.  **Floor (Slate-50):** The base application canvas.
2.  **Surface (White):** Primary containers and cards. These use a 1px border (#E2E8F0) and a very subtle shadow (0px 1px 3px rgba(0,0,0,0.05)).
3.  **Overlay (White):** Modals and dropdowns. These feature a more pronounced shadow (0px 10px 15px -3px rgba(0,0,0,0.1)) to indicate temporary interaction priority.

Avoid heavy blurs or colorful glows; keep shadows neutral and tight to maintain a serious, professional tone.

## Shapes
The design system adopts a **Rounded** profile. A base radius of 8px (0.5rem) is used for standard components like buttons and input fields. Larger containers and cards utilize 12px (0.75rem) to soften the professional edge without appearing "playful." 

This balance ensures the UI feels modern and accessible while maintaining the geometric rigor expected of a B2B compliance tool.

## Components
- **Buttons:** Primary buttons use the Deep Indigo background with white text. Secondary buttons use a white background with a Slate-200 border. Transitions should be instant (150ms) to feel responsive.
- **Chips/Badges:** Used for compliance status. They should feature a low-opacity background of the status color (e.g., Success Emerald at 10% opacity) with high-contrast text for maximum readability.
- **Input Fields:** Use a subtle Slate-200 border that shifts to Indigo on focus. Place labels above the field in `label-md` for clarity.
- **Data Tables:** The core of the platform. Use `body-md` for cell content. Rows should have a subtle hover state (#F8FAFC) and use 1px horizontal dividers only—no vertical borders between columns.
- **Cards:** White background, 1px Slate-200 border. Headers within cards should use `headline-md` and be separated by a full-width divider if the card contains multiple sections.
- **Compliance Indicators:** A specialized icon-plus-label component used to show "GDPR Compliant" or "Opt-Out" status clearly within lead rows.