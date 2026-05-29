# Design System

## Stack
- Next.js 14 (App Router)
- Tailwind CSS
- Shadcn/ui (composants de base uniquement, tout customisé)
- Framer Motion (animations)

## Typographie
- Titres : "Syne" (Google Fonts), font-weight 700
- Corps : "DM Sans", font-weight 400/500
- Import dans layout.tsx via next/font/google

## Couleurs (thème dark par défaut)
- Background : #0A0A0A
- Surface : #141414
- Border : #262626
- Accent : #E8FF47 (jaune électrique)
- Texte : #F5F5F5

## Règles de style
- Coins : border-radius 2px (sharp, pas arrondi)
- Pas de box-shadow, utiliser des borders à la place
- Animations : toujours via Framer Motion, durée 0.3s ease
- Hover states : toujours présents sur éléments interactifs
- Pas de gradients sauf pour les accents

## Composants Shadcn customisés
- Button : variante ghost uniquement, border 1px solid accent au hover
- Card : background surface, border 1px solid border

---

## Implémentation Flask (adaptation)

> L'app supervision-app est en Flask + Jinja2. Le design system ci-dessus est implémenté
> via les équivalents disponibles pour ce stack.

| Design System | Implémentation Flask |
|---------------|----------------------|
| Next.js 14 | Flask 3.x + Jinja2 templates |
| Shadcn/ui | Composants HTML/CSS custom (Tailwind) |
| Framer Motion | CSS transitions (`transition-all duration-200`) |
| next/font/google | `<link>` Google Fonts dans `base.html` |
| Tailwind CSS | Tailwind Play CDN + config inline |

### Config Tailwind (base.html)
```js
tailwind.config = {
  theme: {
    extend: {
      colors: {
        bg:      '#0A0A0A',
        surface: '#141414',
        border:  '#262626',
        accent:  '#E8FF47',
        muted:   '#6B6B6B',
      },
      fontFamily: {
        title: ['Syne', 'sans-serif'],
        body:  ['DM Sans', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: '2px',
        sm: '2px', md: '2px', lg: '2px',
      },
    }
  }
}
```

### Classes utilitaires récurrentes

| Élément | Classes Tailwind |
|---------|-----------------|
| Titre de page | `font-title text-2xl text-[#F5F5F5]` |
| Sous-titre | `text-xs text-muted uppercase tracking-widest` |
| Card | `bg-surface border border-border` |
| Card header | `px-4 py-3 border-b border-border` + `text-[10px] text-muted uppercase tracking-wider font-medium` |
| Input / Select | `bg-bg border border-border text-[#F5F5F5] px-3 py-2.5 text-sm outline-none focus:border-accent transition-colors duration-200` |
| Bouton primaire | `bg-accent text-bg font-title text-xs font-bold px-4 py-2 uppercase tracking-widest hover:bg-[#d4eb3d] transition-colors duration-200` |
| Bouton secondaire | `border border-border text-[#F5F5F5] text-xs px-4 py-2 hover:border-accent transition-colors duration-200 uppercase tracking-wider` |
| Bouton danger | `bg-red-700 text-white text-xs px-4 py-2 uppercase tracking-wider hover:bg-red-600 transition-colors duration-200` |
| Table th | `px-4 py-2.5 text-left text-[10px] text-muted uppercase tracking-wider font-medium` |
| Table td | `px-4 py-3 border-b border-border/50` |
| Table row hover | `hover:bg-[#1c1c1c] transition-colors duration-150` |
| Badge source | `text-[10px] uppercase tracking-wider text-muted border border-border px-1.5 py-0.5` |
| Nav link actif | `border-accent text-accent border` |
| Nav link inactif | `border-transparent text-muted hover:text-[#F5F5F5] hover:border-border border` |
| Lien accent | `text-accent hover:underline` |
| Code inline | `text-xs text-accent` |

### Badges dynamiques (style.css — classes Jinja)
Les classes `crit-*`, `stat-*`, `sev-*` sont définies dans `style.css` car
Tailwind Play CDN ne peut pas purger les classes construites dynamiquement (ex : `crit-{{ incident.criticality }}`).

### Modals
Les modals Bootstrap sont remplacées par l'élément HTML natif `<dialog>` :
```html
<dialog id="myDialog">
  <!-- contenu -->
  <button onclick="this.closest('dialog').close()">Fermer</button>
</dialog>
<button onclick="document.getElementById('myDialog').showModal()">Ouvrir</button>
```
Stylé via `dialog { ... }` et `dialog::backdrop { ... }` dans `style.css`.
