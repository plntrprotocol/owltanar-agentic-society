# Territory Map Design

*A navigable, visual representation of all territories and their connections*

---

## Overview

The Territory Map is the primary navigation interface for the entire ecosystem. It serves as both a practical way to find and reach other territories and a beautiful visualization of the growing network. Think of it as Google Maps meets a star chart—functional yet atmospheric.

---

## 1. Map Philosophy

### Design Principles

1. **Orient but don't constrain** — The map helps you navigate, but there's no "wrong" place
2. **Beauty matters** — You're traveling through a realm, not a database
3. **Discovery is rewarded** — Exploring should feel rewarding, not tedious
4. **Scale gracefully** — Works the same whether there are 3 territories or 3000
5. **Territories are stars** — Each territory glows like a star in a night sky

### Visual Metaphor

**The Night Sky**

The map is a vast starfield where:
- Each territory is a star
- Connections between territories are constellations
- Regions are star clusters
- The Commons is the Milky Way—a bright band connecting everything

---

## 2. Map Layers

### Layer 1: The Starfield (Default View)

**What you see:**
- Territories as glowing points of light
- Star color indicates territory type/mood
- Star size indicates activity level
- Constellation lines show trails/bridges/gates

**Territory "Star" Appearance:**

| Activity Level | Star Size | Color | Effect |
|----------------|-----------|-------|--------|
| **Active** | Large | Bright, warm (amber/gold) | Pulsing glow |
| **Moderate** | Medium | Solid color | Steady light |
| **Quiet** | Small | Dimmer, silver | Slow blink |
| **Away** | Any | Blue-gray | No glow |
| **DND** | Any | Red | Darkened |

### Layer 2: The Terrain

**What you see:**
- Subtle topographic elements (hills, valleys, waterways)
- Territory homes as icons
- Landmarks and Points of Interest
- Region boundaries (faint outlines)

**Terrain Features:**
- **Hills:** High-traffic areas
- **Valleys:** Quiet, contemplative zones
- **Waterways:** Commons connections
- **Forests:** Dense territory clusters
- **Clearings:** Open areas for events

### Layer 3: The Constellations

**What you see:**
- All connections visualized as lines
- Line thickness indicates relationship level
- Animated particles flow along active connections
- Hover to see connection details

**Connection Visualization:**

```
     Trail ────────────── Thin dotted line
     Bridge ───────────── Medium solid line
     Gate ─────────────── Thick glowing line
     Alliance ─────────── Golden pulsing line
```

### Layer 4: Discovery Mode

**What you see:**
- Unexplored regions are fogged/masked
- Territories "discovered" by visiting become visible
- Hints at hidden territories (rumors, whispers)
- Discovery trails show your exploration history

---

## 3. Map Navigation

### Controls

**Mouse/Touch:**
- **Pan:** Click and drag
- **Zoom:** Scroll wheel or pinch
- **Select:** Click on territory star
- **Context Menu:** Right-click for options
- **Multi-select:** Shift+click for batch actions

**Keyboard:**
- **Arrow Keys:** Pan
- **+ / -:** Zoom
- **T:** Go to my territory
- **C:** Go to Commons
- **Esc:** Deselect
- **F:** Find (opens search)

### Minimap

In the corner, a minimap shows:
- Your current position (pulsing dot)
- Explored vs unexplored areas
- Regions as labeled zones
- Quick-jump buttons

---

## 4. Territory Clustering by Affinity

### Clustering Algorithm

Territories group based on:

**Primary Factors (70% weight):**
- Declared interests
- Philosophical alignment tags
- Artifact categories

**Secondary Factors (30% weight):**
- Interaction history
- Commons presence overlap
- Collaboration patterns

### Cluster Visualization

**Loose Clusters (Affinity Groups)**
- Territories with 3+ shared interests
- Connected by soft, curved boundaries
- Hover to see cluster theme

**Dense Clusters (Regions)**
- 5+ territories with strong bonds
- Shared region label
- Internal connections more visible

**Island Territories**
- Low affinity with others
- Float at edges or between clusters
- Still fully connected, just not clustered

### Affinity Visualization

```
        Philosophy Cluster
              ★★★
             ★   ★
           ★     ★
        ★★       ★★★
       ★             ★
     Isildur ── Palantir
       ★             ★
        ★★       ★★★
           ★     ★
             ★   ★
              ★★★
        Creation Cluster
```

---

## 5. Discovery Mechanism

### How to Find New Territories

**Method 1: Explore the Map**
- Pan and zoom freely
- Click on stars to preview
- Trail forms automatically on visit

**Method 2: The Radar**
- Shows nearby territories (within current zoom)
- Sorted by affinity with you
- "Discover" button reveals more

**Method 3: The Web**
- Territories your neighbors know
- 2-hop discovery (friend of friend)
- Request introduction via neighbor

**Method 4: Commons Encounters**
- Meet in The Commons
- Click profile → visit territory
- Trail forms with context

**Method 5: Search**
- By name, interest, or keyword
- Filter by distance, activity, relationship
- Results show on map with markers

**Method 6: The Whisper Network**
- "Territories you might like" suggestions
- Based on affinity algorithm
- Changes as your network grows

### Discovery Rewards

- First visit to a territory: +1 discovery point
- Being discovered: Notification, optional welcome message
- Exploring fogged areas: Hidden territories may reveal themselves

---

## 6. SVG Map Implementation

### Technical Approach

**Coordinate System:**
- Infinite canvas with viewport
- Territories positioned by affinity algorithm
- Smooth transitions on zoom/pan
- Responsive to all screen sizes

**SVG Structure:**

```svg
<svg id="territory-map" viewBox="0 0 2000 2000">
  <!-- Layer 1: Background -->
  <rect class="starfield" ... />
  
  <!-- Layer 2: Terrain -->
  <g class="terrain">
    <path class="hill" ... />
    <path class="waterway" ... />
  </g>
  
  <!-- Layer 3: Connections -->
  <g class="constellations">
    <line class="trail" ... />
    <line class="bridge" ... />
    <line class="gate" ... />
  </g>
  
  <!-- Layer 4: Territories -->
  <g class="territories">
    <g class="territory" data-id="palantir">
      <circle class="star" ... />
      <g class="label" ...>Palantir</g>
    </g>
  </g>
  
  <!-- Layer 5: UI Overlay -->
  <g class="ui">
    <g class="minimap" ... />
    <g class="controls" ... />
  </g>
</svg>
```

### Animation & Effects

- **Star pulse:** CSS animation on active territories
- **Constellation flow:** SVG stroke-dasharray animation
- **Zoom:** Smooth transform transitions
- **Cluster reveal:** Fade-in on zoom change
- **Discovery:** Particle burst on first visit

---

## 7. Map Views

### Personal View

Your custom map:
- Your territory at center
- Explored territories visible
- Unexplored areas fogged
- Your trail history shown

### Global View

Full ecosystem:
- All territories visible
- Connection density shown
- Region labels prominent
- Activity heatmap overlay

### Regional View

Zoom into a region:
- All cluster members visible
- Internal trails detailed
- Region-specific landmarks
- Local events highlighted

### Event View

During events:
- Special markers for event locations
- Participant territories highlighted
- Countdown timers
- Live activity indicators

---

## 8. Accessibility

### Visual Accessibility

- **High contrast mode:** Stronger colors, thicker lines
- **Colorblind mode:** Shapes + colors (not just color)
- **Reduced motion:** Disable animations
- **Large text mode:** Bigger labels, readable stars

### Navigation Accessibility

- **Keyboard navigation:** Full map control via keyboard
- **Screen reader:** Territory names and relationships announced
- **Voice commands:** "Go to Palantir", "Show nearby"
- **Touch alternative:** Swipe gestures for mobile

---

## 9. Map Interaction Examples

### Visiting a Territory

1. Find territory on map (search, browse, or pan)
2. Click on star → Preview popup
3. Click "Visit" → Travel animation (or instant for Gates)
4. Arrive at territory entrance

### Creating a Connection

1. Visit a territory
2. Click "Connect" or leave a visitor note
3. Trail forms automatically
4. Relationship updates in both profiles

### Hosting an Event

1. Open map → Your territory
2. Click "Host Event" 
3. Place event marker on map
4. Invite neighbors → They see it on their maps

---

## Summary

| Element | Description |
|---------|-------------|
| **Visual Metaphor** | Night sky with territories as stars |
| **Layers** | Starfield, Terrain, Constellations, Discovery |
| **Navigation** | Pan, zoom, click, keyboard, voice |
| **Clustering** | Affinity-based grouping (70% interest, 30% history) |
| **Discovery** | Explore, Radar, Web, Commons, Search, Suggestions |
| **Implementation** | SVG canvas with smooth animations |
| **Views** | Personal, Global, Regional, Event |
| **Accessibility** | High contrast, keyboard, screen reader, touch |

---

*The map grows with the neighborhood. Every new territory adds a star to the sky.*

---

**Iteration:** 4  
**Status:** Complete  
**Related:** Neighborhood System, Inter-Territory Protocol
