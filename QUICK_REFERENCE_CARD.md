# Quick Reference Card - Care_4_U Hospitals Design System

## 🎨 Color Palette (Copy-Paste Ready)

```css
/* Primary */
--primary: #5FEABE;              /* Main buttons, accents, success */
--primary-dark: #4AD4A8;         /* Hover states */
--primary-light: #D4F9EC;        /* Soft backgrounds */
--primary-lighter: #E8FCF5;      /* Lightest layer */

/* Dark & Professional */
--dark: #1D1B1B;                 /* Headers, main text */
--white: #FFFFFF;                /* Backgrounds */

/* Accents */
--accent-pink: #FECADA;          /* Alerts, warnings */
--accent-yellow: #E4FECA;        /* Secondary elements */

/* Grays */
--gray: #718096;                 /* Body text */
--gray-light: #cbd5e0;           /* Placeholders */
--gray-lighter: #edf2f7;         /* Borders */
--gray-lightest: #f7fafc;        /* Hover backgrounds */

/* Shadows (Soft Premium) */
--shadow-sm: 0 1px 2px 0 rgba(29, 27, 27, 0.04);
--shadow-md: 0 4px 8px 0 rgba(29, 27, 27, 0.06);
--shadow-lg: 0 8px 16px 0 rgba(29, 27, 27, 0.08);
--shadow-xl: 0 12px 24px 0 rgba(29, 27, 27, 0.10);
```

---

## 🔤 Typography Quick Reference

```css
/* Font Family */
font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;

/* Font Weights */
--font-weight-thin: 100;
--font-weight-light: 300;
--font-weight-regular: 400;
--font-weight-medium: 500;
--font-weight-bold: 700;

/* Font Sizes */
h1: 2.25rem (36px)  Bold   -0.5px letter-spacing
h2: 1.875rem (30px) Bold   -0.4px letter-spacing
h3: 1.5rem (24px)   Bold   -0.2px letter-spacing
h4: 1.25rem (20px)  Medium
h5: 1.125rem (18px) Medium
p:  1rem (16px)     Regular -0.2px letter-spacing
sm: 0.875rem (14px) Regular
xs: 0.75rem (12px)  Medium (Uppercase for labels)
```

---

## 📏 Spacing Scale (Use These Values)

```css
--spacing-xs:  0.5rem   (8px)   → Tight spacing
--spacing-sm:  0.75rem  (12px)  → Small gaps
--spacing-md:  1rem     (16px)  → Standard spacing
--spacing-lg:  1.5rem   (24px)  → Medium spacing
--spacing-xl:  2rem     (32px)  → Large spacing
--spacing-2xl: 3rem     (48px)  → Extra large
--spacing-3xl: 4rem     (64px)  → Massive

/* Common Uses */
Button Padding:     0.625rem 1.25rem
Button Small:       0.375rem 0.875rem
Card Padding:       2rem
Form Input:         0.625rem 0.875rem
Table Cell:         1rem 1.25rem
Section Padding:    2rem 2.25rem
Header Padding:     3rem 2.5rem
```

---

## 🎯 Component Templates

### Button
```html
<button class="btn btn-primary">Click Me</button>
<button class="btn btn-secondary">Secondary</button>
<button class="btn btn-sm btn-primary">Small</button>
<a href="#" class="btn btn-back"><i class="fas fa-arrow-left"></i> Back</a>
```

### Card
```html
<div class="card">
    <h3>Card Title</h3>
    <p>Card content goes here</p>
</div>
```

### Section
```html
<div class="appointments-section">
    <div class="section-header">
        <h2><i class="fas fa-icon"></i> Section Title</h2>
        <div class="patient-count-badge">
            <i class="fas fa-icon"></i>
            <span>5 Items</span>
        </div>
    </div>
    <!-- Content -->
</div>
```

### Form Input
```html
<div class="form-group">
    <label>Patient Name *</label>
    <input type="text" placeholder="Enter name" required>
</div>
```

### Badge
```html
<span class="badge">3 Items</span>
<span class="badge badge-success">Active</span>
<span class="badge badge-secondary">Inactive</span>
```

---

## ⚡ CSS Snippets (Copy & Use)

### New Button Style
```css
.btn-custom {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-sm);
    padding: 0.625rem 1.25rem;
    border-radius: var(--border-radius-lg);
    font-weight: var(--font-weight-medium);
    background: var(--primary);
    color: var(--white);
    transition: all var(--transition-fast);
    box-shadow: var(--shadow-sm);
}

.btn-custom:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}
```

### New Card Style
```css
.card-custom {
    background: var(--white);
    border-radius: var(--border-radius-xl);
    padding: 2rem;
    box-shadow: var(--shadow-md);
    border: 1px solid var(--gray-lighter);
    transition: all var(--transition-base);
}

.card-custom:hover {
    box-shadow: var(--shadow-lg);
    transform: translateY(-2px);
}
```

### New Section
```css
.section-custom {
    background: var(--white);
    border-radius: var(--border-radius-xl);
    padding: 2rem 2.25rem;
    margin-bottom: var(--spacing-2xl);
    box-shadow: var(--shadow-md);
    border: 1px solid var(--gray-lighter);
}
```

### Form Input Focus
```css
.form-group input:focus {
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 0 2px var(--primary-light);
}
```

---

## 📱 Responsive Breakpoints

```css
/* Mobile First Approach */
@media (max-width: 768px) {
    /* Reduce padding */
    padding: 1rem 1.5rem;
    
    /* Stack layouts */
    flex-direction: column;
    
    /* Full width buttons */
    width: 100%;
    
    /* Reduce font sizes */
    font-size: var(--font-size-sm);
    
    /* Single column grids */
    grid-template-columns: 1fr;
}

@media (max-width: 1024px) {
    /* Tablet optimizations */
    grid-template-columns: repeat(2, 1fr);
    padding: 1.5rem 2rem;
}
```

---

## ✅ Common Use Cases

### I want to make a button
```html
<button class="btn btn-primary">Save Changes</button>
```

### I want to create a card with content
```html
<div class="card">
    <h3>Patient Info</h3>
    <p>Content here</p>
</div>
```

### I want a section with header
```html
<div class="appointments-section">
    <div class="section-header">
        <h2>My Patients</h2>
        <span class="patient-count-badge">5 Patients</span>
    </div>
</div>
```

### I want a form field
```html
<div class="form-group">
    <label>Email Address</label>
    <input type="email" placeholder="name@example.com">
</div>
```

### I want a badge
```html
<span class="badge badge-success">Confirmed</span>
```

### I want styling for text
```html
<h2>Page Title</h2>           <!-- 30px, bold, dark -->
<p>Body text content</p>      <!-- 16px, regular, dark -->
<small>Small text</small>     <!-- 14px, regular -->
```

---

## 🚫 DON'Ts (Never Do This)

```css
/* DON'T: Hardcode colors */
❌ color: #5FEABE;
✅ color: var(--primary);

/* DON'T: Use custom shadow values */
❌ box-shadow: 0 10px 20px rgba(0,0,0,0.3);
✅ box-shadow: var(--shadow-md);

/* DON'T: Arbitrary spacing */
❌ padding: 15px;
✅ padding: var(--spacing-sm);

/* DON'T: Custom font sizes */
❌ font-size: 18px;
✅ font-size: var(--font-size-lg);

/* DON'T: Mix px and rem */
❌ padding: 2rem 20px;
✅ padding: 2rem 1.25rem;

/* DON'T: Use pure black */
❌ color: #000;
✅ color: var(--dark);

/* DON'T: Skip transitions */
❌ .btn { }
✅ .btn { transition: all var(--transition-fast); }

/* DON'T: Gradient buttons */
❌ background: linear-gradient(135deg, #5FEABE, #4AD4A8);
✅ background: var(--primary);

/* DON'T: Tight spacing */
❌ padding: 5px;
✅ padding: var(--spacing-sm);

/* DON'T: Heavy shadows */
❌ box-shadow: 0 20px 40px rgba(0,0,0,0.4);
✅ box-shadow: var(--shadow-md);
```

---

## 🎬 Transitions Quick Reference

```css
.element {
    /* Fast (150ms) - buttons, quick feedback */
    transition: all var(--transition-fast);
    
    /* Normal (200ms) - cards, typical interactions */
    transition: all var(--transition-base);
    
    /* Slow (300ms) - modals, important changes */
    transition: all var(--transition-slow);
}
```

---

## 🎨 Color Usage Matrix

| Element | Color | Example |
|---------|-------|---------|
| Primary Button | `--primary` | `.btn-primary` |
| Button Hover | `--primary-dark` | On hover state |
| Button Background | `--white` | Text color |
| Header | `--dark` | `.dashboard-header` |
| Body Text | `--dark` | `<p>` tag |
| Secondary Text | `--gray` | Help text |
| Border | `--gray-lighter` | Card border |
| Badge | `--primary-light` | Background |
| Badge Text | `--primary-dark` | Text color |
| Alert | `--accent-pink` | Background |
| Success | `--success` | Icon color |

---

## 📊 Quick Stats

- **Total Colors**: 11 primary colors
- **Font Weights**: 5 weight options
- **Font Sizes**: 8 size levels
- **Spacing Levels**: 7 scale increments
- **Shadow Depths**: 4 shadow levels
- **Transition Speeds**: 3 timing options
- **Border Radius**: 4 roundness levels
- **Mobile Breakpoint**: 768px
- **Tablet Breakpoint**: 1024px
- **Max Container Width**: 1400px

---

## 🔗 File Locations

- **Main CSS**: `static/css/style.css` (Lines 1-90 for variables)
- **Dashboard CSS**: `static/css/dashboard.css`
- **Design System**: `MODERN_UI_DESIGN_SYSTEM.md`
- **CSS Details**: `CSS_MODERNIZATION_REPORT.md`
- **Visual Ref**: `VISUAL_DESIGN_REFERENCE.md`
- **Dev Guide**: `IMPLEMENTATION_GUIDE.md`

---

## ⏱️ Common Component Build Times

- New button style: 2 minutes
- New card style: 3 minutes
- New section: 5 minutes
- Full page: 20-30 minutes
- Mobile responsive: 10-15 minutes

---

## 🆘 Troubleshooting

**Colors look wrong?**
→ Check you're using `var(--colorname)` not hex codes

**Spacing looks inconsistent?**
→ Use only `var(--spacing-*)` values

**Shadows too dark?**
→ Use `var(--shadow-sm)` or `var(--shadow-md)`, not custom values

**Button too big?**
→ Use standard padding: `0.625rem 1.25rem`

**Text not readable?**
→ Use `color: var(--dark)` for body text

**Responsive broken?**
→ Test at 768px breakpoint, use `@media (max-width: 768px)`

**Hover effect missing?**
→ Add `transition: all var(--transition-fast);` and define hover state

---

## 🎁 Ready-to-Copy Snippets

### Dashboard Header
```html
<div class="dashboard-header">
    <div class="header-content">
        <h1><i class="fas fa-stethoscope"></i> Dashboard Title</h1>
        <p class="welcome-message">Welcome message here</p>
    </div>
    <a href="#" class="btn btn-back"><i class="fas fa-arrow-left"></i> Back</a>
</div>
```

### Patient Card
```html
<div class="patient-info-card">
    <div class="info-header">
        <div class="patient-avatar"><i class="fas fa-user-circle"></i></div>
        <div class="patient-details">
            <h2>Patient Name</h2>
            <div class="detail-grid">
                <div class="detail-item"><i class="fas fa-envelope"></i> <span>email@example.com</span></div>
                <div class="detail-item"><i class="fas fa-phone"></i> <span>(555) 123-4567</span></div>
            </div>
        </div>
    </div>
    <div class="info-stats">
        <div class="stat-box">
            <div class="stat-icon"><i class="fas fa-calendar-check"></i></div>
            <h3>5</h3>
            <p>Appointments</p>
        </div>
    </div>
</div>
```

---

**Quick Reference Card v1.0**  
**Updated**: February 2026  
**Status**: ✅ Ready to Use  

*Print this page for your desk or bookmark it in your browser!*
