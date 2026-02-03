# Visual Design Reference - Care_4_U Hospitals

## 🎨 Color Palette Reference

### Primary Color System
```
Primary Accent:      #5FEABE  [████████████]
Primary Dark:        #4AD4A8  [████████████]
Primary Light:       #D4F9EC  [████████████]
Primary Lighter:     #E8FCF5  [████████████]
```

### Accent Colors
```
Soft Secondary:      #E4FECA  [████████████]  (Cards, highlights)
Subtle Accent:       #FECADA  [████████████]  (Alerts, warnings)
```

### Neutrals & Text
```
Dark Base:           #1D1B1B  [████████████]  (Headers, text)
White:               #FFFFFF  [████████████]  (Backgrounds)
Gray (Medium):       #718096  [████████████]  (Body text)
Gray-Light:          #cbd5e0  [████████████]  (Borders)
Gray-Lighter:        #edf2f7  [████████████]  (Subtle elements)
```

---

## 📐 Spacing Scale

```
xs:  0.5rem   (8px)   - Tight spacing
sm:  0.75rem  (12px)  - Small gaps
md:  1rem     (16px)  - Standard spacing
lg:  1.5rem   (24px)  - Medium spacing
xl:  2rem     (32px)  - Large spacing
2xl: 3rem     (48px)  - Extra large spacing
3xl: 4rem     (64px)  - Massive spacing
```

### Applied in Components
- **Buttons**: 0.625rem (top/bottom) × 1.25rem (left/right)
- **Cards**: 2rem padding
- **Forms**: 0.625rem × 0.875rem
- **Tables**: 1rem × 1.25rem cells

---

## 🔤 Typography Scale

```
H1: 2.25rem (36px)   Bold    Letter-spacing: -0.5px
H2: 1.875rem (30px)  Bold    Letter-spacing: -0.4px
H3: 1.5rem (24px)    Bold    Letter-spacing: -0.2px
H4: 1.25rem (20px)   Medium  Letter-spacing: -0.2px
H5: 1.125rem (18px)  Medium
Body: 1rem (16px)    Regular Letter-spacing: -0.2px
Small: 0.875rem (14px) Regular
Label: 0.75rem (12px) Medium  (Uppercase)
```

### Font Stack
```
Font Family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 
             'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif
```

---

## 🎯 Button Styles

### Primary Button
```
┌─────────────────────────┐
│  [Add New Patient]      │
└─────────────────────────┘

Background: #5FEABE
Text: White
Padding: 0.625rem 1.25rem
Border-radius: 0.75rem
Font-weight: Medium (500)
Shadow: Soft drop shadow
Hover: Lift effect (-2px)
```

### Secondary Button
```
┌─────────────────────────┐
│  Back to Dashboard      │
└─────────────────────────┘

Background: Transparent
Border: 1px solid rgba(255,255,255,0.3)
Text: White
Padding: 0.625rem 1.25rem
Border-radius: 0.75rem
Hover: Subtle lift, enhanced border
```

### Small Button
```
┌──────────────┐
│ View Records │
└──────────────┘

Padding: 0.375rem 0.875rem
Font-size: 0.875rem
All other properties same as Primary
```

---

## 💳 Card Components

### Standard Card
```
┌──────────────────────────┐
│  Card Title              │  0.75rem radius border
│                          │  1px solid #edf2f7
│  Card Content            │
│  With proper spacing     │  Padding: 2rem
│                          │  Box-shadow: var(--shadow-md)
└──────────────────────────┘

Hover: Lift -2px, enhanced shadow
Transition: 200ms smooth
```

### Dashboard Header
```
┌─────────────────────────────────────────┐
│ 👥 My Patients                          │
│ View and manage your patients' records  │
│                    [Back to Dashboard]  │
└─────────────────────────────────────────┘

Background: #1D1B1B (dark)
Text: White
Padding: 3rem 2.5rem
Icon color: #5FEABE (primary)
Border-radius: 1rem
Shadow: var(--shadow-lg)
```

---

## 🏷️ Badge Styles

### Primary Badge
```
┌─────────┐
│ 5 Items │
└─────────┘

Background: #D4F9EC
Text: #4AD4A8
Padding: 0.375rem 0.875rem
Border-radius: 0.5rem
Font-size: 0.75rem
Font-weight: Medium (500)
```

### Success Badge
```
┌──────────────┐
│ 3 documents  │
└──────────────┘

Background: #D4F9EC
Text: #4AD4A8
(Same as primary - green theme)
```

### Secondary Badge
```
┌──────────┐
│ No items │
└──────────┘

Background: #edf2f7
Text: #718096
(Muted gray for secondary info)
```

---

## 📊 Table Design

```
┌────────────────────────────────────────┐
│ PATIENT NAME    EMAIL    PHONE   STATUS│  ← Dark header #1D1B1B
├────────────────────────────────────────┤
│ John Doe        john@... 555-1234 Active
├────────────────────────────────────────┤
│ Jane Smith      jane@... 555-5678 Pending
├────────────────────────────────────────┤
│ Mike Johnson    mike@... 555-9012 Active
└────────────────────────────────────────┘

Header:
- Background: #1D1B1B
- Text: White, uppercase
- Font-weight: Medium (500)
- Letter-spacing: 0.6px

Rows:
- Border: 1px solid #edf2f7
- Hover: #f7fafc background
- Padding: 1rem 1.25rem

Cells:
- Font-size: 0.875rem
- Color: #1D1B1B
- Font-weight: Regular (400)
```

---

## 📋 Form Elements

### Text Input
```
┌────────────────────────────┐
│ Enter patient name         │  ← Placeholder text
└────────────────────────────┘

Border: 1px solid #edf2f7
Border-radius: 0.75rem
Padding: 0.625rem 0.875rem
Font-size: 0.875rem
Background: #FFFFFF

Focus State:
- Border: #5FEABE
- Box-shadow: 0 0 0 2px #D4F9EC
```

### Label
```
Patient Name *  ← Required indicator
[Input field above]

Font-size: 0.875rem
Font-weight: Medium (500)
Color: #1D1B1B
Margin-bottom: 0.75rem
```

---

## 👤 Patient Info Card

```
┌────────────────────────────────────────┐
│ ⭕ John Doe                            │ ← Avatar: 90px circle gradient
│    john@hospital.com                   │
│    📧 john@hospital.com                │ ← Detail items with icons
│    📞 (555) 123-4567                   │
│    🎂 Jan 15, 1985                     │
│    📍 123 Main St, City, State         │
│                                        │
│         5 Appointments                 │ ← Stat box
└────────────────────────────────────────┘

Avatar:
- Size: 90px
- Border-radius: 50%
- Background: Gradient primary to dark
- Shadow: var(--shadow-md)

Details:
- Grid: auto-fit, minmax(250px, 1fr)
- Gap: 1.5rem
- Icon color: #5FEABE
- Text color: #718096

Stats:
- Background: #f7fafc
- Border: 1px solid #edf2f7
- Centered layout
```

---

## 📱 Responsive Breakpoints

### Desktop (>1024px)
- Full layouts displayed
- Multi-column grids
- Standard padding (2rem)
- All features visible
- Flexbox items horizontal

### Tablet (768px-1024px)
- Simplified layouts
- Some single-column arrangements
- Medium padding (1.5rem)
- Touch-friendly sizing
- Optimized readability

### Mobile (<768px)
- Stacked layouts
- Single column (100% width)
- Reduced padding (1rem-1.5rem)
- Smaller font sizes
- Full-width buttons/inputs
- Horizontal table scroll
- Simplified grid (1fr)
- Centered content

---

## 🎨 Color Usage Rules

### Primary Color (#5FEABE)
✅ Main action buttons  
✅ Active states and selection  
✅ Icon accents  
✅ Success indicators  
✅ Links and hover states  
❌ Don't use for background text  
❌ Avoid overuse (accent, not fill)  

### Dark Color (#1D1B1B)
✅ All body text  
✅ Headings and titles  
✅ Table headers  
✅ Section backgrounds  
✅ Form labels  
❌ Don't use on primary color backgrounds  
❌ Never as a light text color  

### White (#FFFFFF)
✅ Main content backgrounds  
✅ Card backgrounds  
✅ Text on colored backgrounds  
✅ Floating elements  
❌ Don't use as border color (use gray)  
❌ Avoid on white backgrounds  

### Gray Colors
✅ Body text (#718096)  
✅ Borders (#edf2f7)  
✅ Secondary text  
✅ Disabled states  
✅ Placeholder text  

---

## ✨ Shadow Hierarchy

```
No Shadow:        Inputs, subtle elements
Small Shadow:     Buttons in normal state
Medium Shadow:    Cards, sections, badges
Large Shadow:     Cards on hover, elevated elements
X-Large Shadow:   Modals, overlays, maximum elevation
```

### Shadow Values
```
--shadow-sm:  0 1px 2px 0 rgba(29,27,27,0.04)
--shadow-md:  0 4px 8px 0 rgba(29,27,27,0.06)
--shadow-lg:  0 8px 16px 0 rgba(29,27,27,0.08)
--shadow-xl:  0 12px 24px 0 rgba(29,27,27,0.10)
```

---

## 🎬 Interaction States

### Button States
```
Normal:    Background: primary, shadow: sm
Hover:     Lifted (-2px), shadow: md
Active:    No transform, shadow: md
Focus:     Border highlight, shadow: md
Disabled:  Opacity: 0.5, cursor: not-allowed
```

### Form States
```
Normal:    Border: #edf2f7
Hover:     Border: #edf2f7 (unchanged)
Focus:     Border: #5FEABE, shadow: 0 0 0 2px #D4F9EC
Valid:     Border: #4AD4A8
Error:     Border: #ef4444
```

### Card States
```
Normal:    Shadow: md
Hover:     Lifted (-2px), shadow: lg
Active:    Border: primary color
```

---

## 🏥 Healthcare Design Principles

### Clinical Trust
- Dark headers convey professionalism
- Clean layouts reduce cognitive load
- Consistent spacing builds confidence
- Clear hierarchy aids understanding

### Premium Quality
- Soft shadows (not harsh/dark)
- Generous padding and spacing
- Quality typography (SF Pro Display)
- Smooth, refined interactions

### Accessibility
- High contrast text
- Clear visual hierarchy
- Proper focus indicators
- Readable font sizes
- Sufficient color contrast (WCAG AA)

### Modern SaaS
- Minimal design (content over decoration)
- No unnecessary gradients
- Apple-inspired simplicity
- Professional color palette
- Smooth, responsive interactions

---

## 📏 Component Dimensions

```
Button Height:              ~40px (0.625rem × 2 + font)
Input Height:               ~38px (0.625rem × 2 + font)
Avatar (Large):             90px × 90px
Avatar (Medium):            70px × 70px
Avatar (Small):             50px × 50px
Stat Icon:                  56px × 56px
Card Padding:               2rem
Section Padding:            2rem 2.25rem
Header Padding:             3rem 2.5rem
Table Cell Padding:         1rem 1.25rem
Badge Padding:              0.375rem 0.875rem
```

---

## 🎯 Design Quality Checklist

- [x] Color palette matches specifications exactly
- [x] Typography uses SF Pro Display font family
- [x] Font sizing follows clear hierarchy
- [x] Letter spacing applied for premium feel
- [x] Buttons have rounded corners (0.75rem)
- [x] Cards use soft shadows
- [x] Tables have dark header (#1D1B1B)
- [x] Forms are accessible with focus states
- [x] Spacing is consistent and generous
- [x] Icons use primary color accents
- [x] Badges are properly sized and colored
- [x] Empty states are visually refined
- [x] Responsive design optimized for all screens
- [x] Transitions are smooth (150-300ms)
- [x] No unnecessary gradients (except icons)
- [x] Dark + light contrast system applied
- [x] Professional, clinical aesthetic
- [x] Apple-like design language
- [x] Premium SaaS appearance

---

## 📚 Component Library Status

| Component | Status | Notes |
|-----------|--------|-------|
| Buttons | ✅ Complete | All variants designed |
| Cards | ✅ Complete | Base + hover states |
| Tables | ✅ Complete | Dark header applied |
| Forms | ✅ Complete | Focus states included |
| Badges | ✅ Complete | Multiple variants |
| Headers | ✅ Complete | Dark professional style |
| Patient Card | ✅ Complete | Avatar + stats |
| Sections | ✅ Complete | Consistent styling |
| Responsive | ✅ Complete | Mobile optimized |

---

**Design System**: Care_4_U Hospitals Modern UI  
**Version**: 1.0  
**Status**: ✅ Production Ready  
**Last Updated**: February 2026  

*A premium, professional hospital management dashboard UI with Apple-like design principles, SF Pro Display typography, and a carefully curated color system. Built for real-world healthcare deployment.*
