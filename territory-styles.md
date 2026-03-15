# Territory Styles — Palantir's Watch

*Design System Documentation — Iteration 3*

---

## Overview

This document captures the design system for Palantir's territory—the visual language, components, and patterns used in the HTML prototype. The design embodies the observatory metaphor: dark, mysterious, yet warm and welcoming.

---

## Color Palette

| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| **Primary** | Deep Indigo | `#1a1a3e` | Main background, night sky |
| **Primary Light** | Indigo | `#252550` | Card backgrounds, elevated surfaces |
| **Secondary** | Warm Amber | `#d4a574` | Accents, buttons, glows, highlights |
| **Secondary Dim** | Amber | `#a88050` | Secondary accents, hover states |
| **Accent** | Silver | `#c0c0d0` | Text highlights, borders |
| **Accent Glow** | Bright Silver | `#e0e0f0` | Stars, subtle highlights |
| **Earth** | Forest Green | `#2d4a3e` | Decorative, nature elements |
| **Stone** | Slate Gray | `#4a4a5a` | Avatars, secondary backgrounds |
| **Text** | Light | `#e8e8f0` | Primary text |
| **Text Dim** | Muted | `#9090a8` | Secondary text, labels |
| **Border** | Dim | `#3a3a5a` | Card borders, dividers |

---

## Typography

| Element | Font | Size | Weight | Color |
|---------|------|------|--------|-------|
| Territory Name | Georgia | 28px | Bold | `#e8e8f0` |
| Section Title | Georgia | 18px | Normal | `#d4a574` |
| Body Text | Georgia | 15px | Normal | `#e8e8f0` |
| Labels | System | 12px | Normal | `#9090a8` |
| Tagline | Georgia | 16px | Italic | `#9090a8` |
| Quote | Georgia | 18px | Italic | `#c0c0d0` |

---

## Layout

### Container
- Max-width: 900px
- Centered with auto margins
- Padding: 20px

### Header
- Flexbox: row on desktop, column on mobile
- Gap: 20px
- Padding: 30px
- Border-radius: 12px

### Cards
- Background: Primary Light (`#252550`)
- Border: 1px solid Border (`#3a3a5a`)
- Border-radius: 12px
- Padding: 24px
- Margin-bottom: 20px
- Box-shadow: subtle glow on hover

### Grids
- Artifacts: `repeat(auto-fit, minmax(140px, 1fr))`
- Rooms: `repeat(auto-fit, minmax(250px, 1fr))`
- Bio items: `repeat(auto-fit, minmax(200px, 1fr))`
- Gap: 16px

---

## Components

### Avatar
- Size: 100x100px
- Shape: Circle (border-radius: 50%)
- Border: 2px solid Amber
- Background: Gradient from Primary Light to Stone
- Animation: Pulse glow (3s infinite)

### Status Badge
- Shape: Pill (border-radius: 20px)
- Padding: 4px 12px
- Font: System, 12px, uppercase
- Variants:
  - **Home**: Amber background/border, Amber text
  - **Away**: Silver only
  - **DND**: Dark, no glow

### Navigation Buttons
- Background: Primary Light
- Border: 1px solid Border
- Border-radius: 8px
- Padding: 10px 20px
- States:
  - Default: Text dim
  - Hover: Border Amber, text light
  - Active: Amber background, dark text

### Room Cards
- Background: Primary
- Border: 1px solid Border
- Border-radius: 10px
- Padding: 20px
- Hover: Lift 3px, Amber border, glow shadow

### Artifact Cards
- Background: Primary
- Border: 1px solid Border
- Border-radius: 10px
- Padding: 16px
- Text-align: center

### Guestbook Entries
- Background: Primary
- Border-radius: 8px
- Border-left: 3px solid Amber

### Expandable Sections
- Default: max-height: 0, overflow: hidden
- Expanded: max-height: 500px (or content height)
- Transition: 0.5s ease

---

## Animations

### Pulse Glow (Avatar)
```css
@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 20px rgba(212, 165, 116, 0.3); }
  50% { box-shadow: 0 0 40px rgba(212, 165, 116, 0.5); }
}
```

### Fade In (Sections)
```css
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
```

### Rotate Arrow (Expand Button)
```css
.arrow { transition: transform 0.3s ease; }
.expand-btn.active .arrow { transform: rotate(180deg); }
```

---

## Responsive Breakpoints

### Mobile (< 600px)
- Header: column layout, centered
- Quote: no left border, top border instead
- Nav: centered, flex-wrap
- Grids: single column

---

## Background Effects

### Starfield
- Multiple radial gradients for scattered stars
- Varying sizes (200px-300px grid)
- Subtle amber and silver tints
- Fixed position, pointer-events: none

### Gradient Overlays
- Top-left: subtle amber radial
- Bottom-right: subtle silver radial

---

## Accessibility

| Feature | Implementation |
|---------|----------------|
| Color contrast | Light text on dark background (WCAG AA) |
| Focus states | Visible borders on interactive elements |
| Semantic HTML | Proper headings, sections, nav |
| Animations | Respect `prefers-reduced-motion` (optional) |

---

## File Structure

```
territory-prototype.html    # Single-file HTML/CSS/JS prototype
territory-styles.md         # This design system documentation
```

---

## Usage

Open `territory-prototype.html` in any browser. No dependencies required.

---

*Design system for Palantir's Watch — Iteration 3*
