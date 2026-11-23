# FinBridge Design System & Screen Inventory

> **Source of Truth**: Google Stitch MCP Project `FinBridge Financial Reconciliation Platform` (`projects/10778036521604221916`)  
> **Extraction Date**: November 22, 2026  
> **Status**: Approved Design Baseline — Extracted directly from Stitch prototype screens.

---

## 1. Color Palette

FinBridge uses a high-trust commercial financial palette combining deep midnight navy, rich bridge indigo, trust emerald, sky blue, and amber review accents.

### Brand & Core Colors

| Token Name | Hex Code | Role & Usage |
| :--- | :--- | :--- |
| `midnight-navy` | `#101B32` | Shell background, primary sidebar, high-emphasis text, brand anchors |
| `bridge-indigo` | `#5146E5` | Primary interactive brand color, active navigation tabs, primary CTAs |
| `trust-emerald` | `#16A37B` | Positive verification indicators, match confidence badges, SOC 2 compliance pills |
| `sky-blue` | `#6B9DFF` | Secondary accents, informational indicators, active focus rings |
| `review-amber` | `#E9A23B` | Review queue warnings, pending approval alerts, priority flags |
| `cloud-white` | `#F5F7FB` | Neutral page backdrop, low-contrast container surfaces |

### Surface & Container System (Light Mode Primary)

| Token Name | Hex Code | Description |
| :--- | :--- | :--- |
| `surface` | `#F5F7FB` | Base application background behind containers and sidebars |
| `surface-container-lowest` | `#FFFFFF` | Primary card background, table background, modal dialogs, input fills |
| `surface-container-low` | `#FBFCFF` | Subtle card background, hovered table rows, secondary panels |
| `surface-container` | `#EFF1F5` | Table headers, secondary toolbar pills, inactive segmented tabs |
| `surface-container-high` | `#E0E3E6` | High-contrast divider panels, active tab highlights |
| `outline` | `#74777B` | Inactive borders, placeholder text, secondary icons |
| `outline-variant` | `#E0E3E6` | Subtle dividers, card borders, table row borders (`divide-outline-variant`) |

### Semantic State Colors

| State | Primary Hex | Container Hex | Text / Foreground | Typical Usage |
| :--- | :--- | :--- | :--- | :--- |
| **Primary** | `#5146E5` | `#F2EFFF` | `#1F00A4` / `#FFFFFF` | Primary buttons, active tabs, brand icons |
| **Secondary** | `#101B32` | `#EDF0FF` | `#101B32` / `#FFFFFF` | High-emphasis headers, navigation items |
| **Success** | `#006C50` | `#E6F8F2` | `#003828` | Exact match confirmed, verified ledger entry, SOC 2 active |
| **Warning** | `#845400` | `#FFF4E5` | `#462A00` | Review queue items, variance detected, pending supervisor approval |
| **Error** | `#BA1A1A` | `#FFEDEA` | `#690005` | Unmatched transaction, rule violation, integration HTTP 500 error |
| **Info** | `#1D5BB9` | `#EDF0FF` | `#002E6A` | Audit logs, system health notices, ERP synchronization progress |

---

## 2. Typography

FinBridge uses **Inter** for all interface copy, headings, and labels, paired with **JetBrains Mono** for financial values, transaction IDs, GL accounts, and timestamps.

### Font Families
- **Display / Headline / Body / Label**: `"Inter", sans-serif`
- **Monospace / Financial Data**: `"JetBrains Mono", monospace`

### Type Scale Specification

| Type Token | Font Size | Line Height | Letter Spacing | Default Weight | Target Elements |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `display-md` | `32px` | `40px` | `-0.5px` | 600 (Semibold) | Page hero banners, welcome headings |
| `display-md-mobile` | `24px` | `32px` | `-0.25px` | 600 (Semibold) | Mobile hero headings |
| `headline-lg` | `24px` | `32px` | `-0.25px` | 600 (Semibold) | Section headers, modal titles, auth card titles |
| `headline-md` | `20px` | `28px` | `-0.15px` | 600 (Semibold) | Widget headings, card titles, drawer headers |
| `title-lg` | `16px` | `24px` | `0px` | 600 (Semibold) | Navigation brand title, table section titles |
| `title-md` | `14px` | `20px` | `0px` | 600 (Semibold) | Table row primary cell, card subtitles |
| `body-lg` | `15px` | `22px` | `0px` | 400 (Regular) | Introductory copy, auth description |
| `body-md` | `14px` | `20px` | `0px` | 400 (Regular) | Standard body copy, form field text |
| `body-sm` | `12px` | `16px` | `+0.1px` | 400 (Regular) | Helper text, secondary descriptions, table metadata |
| `label-lg` | `14px` | `20px` | `0px` | 500 (Medium) | Standard button labels, tab labels |
| `label-md` | `12px` | `16px` | `+0.2px` | 500 (Medium) | Form labels, table header titles |
| `label-sm` | `11px` | `14px` | `+0.4px` | 600 (Semibold) | Status badges, metric change indicators, tag pills |
| `mono-md` | `13px` | `18px` | `0px` | 500 (Medium) | Currency amounts, ledger debits/credits |
| `mono-sm` | `12px` | `16px` | `0px` | 400 (Regular) | Transaction IDs, correlation IDs, bank timestamps |

---

## 3. Font Weights

| Weight Token | Value | Applied Elements |
| :--- | :--- | :--- |
| `font-normal` | 400 | Body prose, description paragraphs, secondary cells |
| `font-medium` | 500 | Button text, form field labels, metadata tokens |
| `font-semibold` | 600 | Headings, card titles, table headers, status badges |
| `font-bold` | 700 | Emphasized financial deltas, primary metric figures |

---

## 4. Spacing System

| Token | Exact Value | Purpose |
| :--- | :--- | :--- |
| `gutter-xs` | `4px` | Micro-spacing, badge padding, icon gap |
| `gutter-sm` | `8px` | Button content gap, list item gap, pill spacing |
| `gutter-md` | `16px` | Card internal gap, form row spacing, grid gap |
| `gutter-lg` | `24px` | Section gap, container margins, modal padding |
| `gutter-xl` | `32px` | Major section separator, dashboard panel margins |
| `section` | `40px` | Vertical spacing between major page segments |
| `page-margin` | `24px` | Left/right page margins on desktop viewports |

---

## 5. Border Radius

| Token | Value | Typical Usage |
| :--- | :--- | :--- |
| `rounded-xs` | `4px` | Checkboxes, tiny tag pills, organization avatar squares |
| `rounded-sm` | `6px` | Small action buttons, input fields, date picker cells |
| `rounded` (DEFAULT) | `8px` | Standard buttons, form text inputs, select dropdowns, search bars |
| `rounded-md` | `10px` | Secondary cards, dropdown menus |
| `rounded-lg` | `12px` | Inner comparison boxes, warning callouts, code containers |
| `rounded-xl` | `16px` | Primary cards, modal dialogs, drawer panels, metric widgets |
| `rounded-full` | `9999px` | User avatar badges, status indicators, counter pills |

---

## 6. Shadows & Elevation

| Token | CSS Definition | Usage |
| :--- | :--- | :--- |
| `shadow-sm` | `0 1px 2px 0 rgb(0 0 0 / 0.05)` | Standard card elevation, table wrappers |
| `shadow` | `0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)` | Hovered cards, dropdown menus |
| `shadow-md` | `0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)` | Floating toolbars, drawer handles |
| `shadow-lg` | `0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)` | Approval modals, drawer panels, popover overlays |

---

## 7. Buttons

### Primary Action Button
- **Classes**: `px-4 py-2.5 rounded bg-primary text-on-primary font-label text-label-lg hover:bg-on-primary-container focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 transition-colors duration-state-change disabled:opacity-70 inline-flex items-center justify-center gap-2`
- **Variants**: Standard size (`py-2.5 px-4`), Compact size (`py-1.5 px-3`).

### Secondary / Outline Button
- **Classes**: `px-4 py-2.5 rounded border border-outline-variant bg-surface-container-lowest text-on-surface font-label text-label-md hover:bg-surface-container transition-colors inline-flex items-center justify-center gap-2`

### Danger Button (Reject Match / Delete)
- **Classes**: `px-4 py-2.5 rounded border border-error/30 bg-error-container text-on-error-container font-label text-label-md hover:bg-error hover:text-on-error transition-colors inline-flex items-center justify-center gap-2`

### Ghost / Icon Button
- **Classes**: `w-8 h-8 rounded border border-outline-variant inline-flex items-center justify-center text-on-surface-muted hover:text-on-surface hover:bg-surface-container transition-colors`

---

## 8. Form Fields & Input Controls

### Text Input
- **Classes**: `w-full rounded px-3.5 py-2.5 bg-surface-container-lowest border border-outline-variant text-on-surface font-body text-body-md placeholder:text-outline focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all`
- **Error State**: `border-error focus:border-error focus:ring-error text-on-surface` accompanied by `<p class="font-body text-body-sm text-error flex items-center gap-1">`

### Checkbox
- **Classes**: `rounded-xs border-outline-variant text-primary focus:ring-primary w-4 h-4 cursor-pointer`

### Select Dropdown
- **Classes**: `w-full rounded px-3.5 py-2.5 bg-surface-container-lowest border border-outline-variant text-on-surface font-body text-body-md focus:border-primary focus:ring-1 focus:ring-primary`

---

## 9. Tables System

### Structural Pattern
```html
<div class="w-full bg-surface-container-lowest border border-outline-variant rounded-xl overflow-hidden shadow-sm">
  <table class="w-full text-left border-collapse tabular-nums">
    <thead class="bg-surface-container border-b border-outline-variant font-label text-label-sm text-on-surface-muted">
      <tr>
        <th class="py-3 px-4">Transaction ID</th>
        <th class="py-3 px-3">Date</th>
        <th class="py-3 px-3 text-right">Amount</th>
        <th class="py-3 px-4 text-right">Action</th>
      </tr>
    </thead>
    <tbody class="divide-y divide-outline-variant font-body text-body-sm">
      <tr class="hover:bg-surface-container-low cursor-pointer transition-colors">
        <td class="py-3.5 px-4 font-mono text-mono-sm">TXN-2026-88412</td>
        <td class="py-3.5 px-3">Nov 21, 2026</td>
        <td class="py-3.5 px-3 text-right font-mono text-mono-md font-semibold">$14,820.80</td>
        <td class="py-3.5 px-4 text-right">...</td>
      </tr>
    </tbody>
  </table>
</div>
```

- **Headers**: Sticky capable, `bg-surface-container`, `text-on-surface-muted`, `text-label-sm` (uppercase / tracked label styling).
- **Cells**: Padding `py-3.5 px-4`, dividers `divide-y divide-outline-variant`.
- **Numbers / Currencies**: Always right-aligned (`text-right`), styled with `font-mono` and `tabular-nums`.

---

## 10. Navigation Architecture

### Left Sidebar (Desktop)
- **Width**: `w-64 shrink-0`
- **Background**: `bg-midnight-navy text-on-secondary`
- **Border**: `border-r border-midnight-navy`
- **Brand Header**: 28x28 geometric FinBridge icon, title `font-headline text-title-lg text-on-secondary`, subtitle `font-label text-label-sm text-on-secondary/60`.
- **Active Navigation Item**: `bg-bridge-indigo text-on-primary rounded font-label text-label-lg` with optional badge (`bg-warning-container text-on-warning-container px-1.5 rounded-full font-label text-label-sm`).
- **Inactive Navigation Items**: `text-on-secondary/80 hover:bg-on-secondary/10 hover:text-on-secondary rounded transition-colors`.
- **Bottom Trust Anchor**: `p-4 m-3 rounded-lg bg-on-secondary/5 border border-on-secondary/10` featuring green SOC 2 audit pill and period lock indicator.

### Top Navigation Bar (Header)
- **Height**: `h-16 sticky top-0 z-20`
- **Background**: `bg-surface-container-lowest border-b border-outline-variant px-6`
- **Elements**: Organization selector pill, breadcrumbs (`chevron_right`), notification bell with active unread dot, user profile card with role tag and Sign Out action.

---

## 11. Cards & Metric Widgets

### KPI Metric Card
- **Container**: `bg-surface-container-lowest border border-outline-variant rounded-xl p-5 shadow-sm flex flex-col justify-between`
- **Metric Figure**: `font-headline text-display-md text-on-surface tabular-nums`
- **Sparkline / Trend**: SVG stroke with positive green (`#16A37B`) or warning amber (`#E9A23B`) delta.

---

## 12. Modals and Drawers

### Approval Modals (A, B, C)
- **Overlay**: Fixed backdrop `bg-midnight-navy/60 backdrop-blur-sm z-50 flex items-center justify-center p-4`
- **Dialog Container**: `w-full max-w-xl bg-surface-container-lowest border border-outline-variant rounded-xl shadow-lg overflow-hidden`
- **Header**: Icon badge (`bg-primary-container text-primary`), title `font-title text-title-lg`, close button.
- **Body**: Side-by-side financial comparison (`grid grid-cols-2 gap-4`), delta comparison table, AI evidence summary.
- **Footer**: `px-6 py-4 bg-surface-container-low border-t border-outline-variant flex items-center justify-end gap-3` with Secondary Cancel and Primary Approve Match buttons.

### Exception Management Split Drawer
- **Placement**: Right-side sliding drawer (Desktop `w-[540px] border-l border-outline-variant bg-surface-container-lowest shadow-lg`)
- **Tabs**: Segmented control (`Evidence`, `Audit Log`, `Ledger Postings`)
- **Actions**: Approve Match, Override Reason dropdown, Flag for Controller Review.

---

## 13. Responsive Layouts & Breakpoints

| Breakpoint | Width | Shell Adaptation | Table Adaptation |
| :--- | :--- | :--- | :--- |
| **Desktop** | `1440px` (or `1280px`) | Fixed 64-width sidebar, top navbar, multi-column grid (`grid-cols-12`) | Full multi-column tables with inline action buttons |
| **Tablet** | `768px` | Collapsible sidebar, compact tables, 2-column KPI grid | Truncated metadata columns, overflow horizontal scroll |
| **Mobile** | `390px` | Hidden sidebar with hamburger drawer, single-column stack, bottom action sticky bar | Card list representation or swipeable table views |

---

## 14. Complete Screen Inventory

Below is the verified inventory of all **47 screens** retrieved from Google Stitch project `FinBridge Financial Reconciliation Platform` (`projects/10778036521604221916`):

| # | Screen Title | Device / Viewport | Dimensions | Node Identifier | Operational Purpose in FinBridge |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **Dashboard — Desktop** | DESKTOP | 1440 × 1122 | `node_9258306724721510631` | Primary financial command center: KPI cards, match trend charts, quick actions, and recent activity. |
| 2 | **Dashboard — Mobile** | MOBILE | 390 × 884 | `node_1488620636945891804` | Mobile-optimized financial dashboard with stacked cards and quick review indicators. |
| 3 | **Dashboard — Tablet** | TABLET | 768 × 1024 | `node_5952107912489785733` | 2-column tablet layout for controllers monitoring reconciliation on iPad / tablet devices. |
| 4 | **Login — Desktop** | DESKTOP | 1440 × 1024 | `node_11403169793294596678` | Split-screen authentication: Midnight Navy trust & compliance panel (left) and clean white credentials card (right). |
| 5 | **Login — Mobile** | MOBILE | 390 × 884 | `node_4252057924310348366` | Mobile login with organization workspace selection and biometric / password inputs. |
| 6 | **Create Account — Desktop** | DESKTOP | 1440 × 1024 | `node_11565003645869778419` | Corporate user registration with organization details, work email, and role selection. |
| 7 | **Create Account — Mobile** | MOBILE | 390 × 884 | `node_2370049281170469325` | Mobile multi-step onboarding registration flow. |
| 8 | **Forgot Password — Desktop** | DESKTOP | 1440 × 1024 | `node_11359656948265991361` | Password reset self-service with SOC 2 compliance verification. |
| 9 | **Forgot Password — Mobile** | MOBILE | 390 × 884 | `node_14742210310413521462` | Mobile password recovery screen. |
| 10 | **Email Verification — Desktop** | DESKTOP | 1440 × 1024 | `node_7268878732298554833` | 6-digit OTP and secure link verification screen with pending, verified, and expired states. |
| 11 | **Email Verification — Mobile** | MOBILE | 390 × 884 | `node_11630219187771150105` | Mobile OTP verification view with resend countdown. |
| 12 | **Bank Statements — Desktop** | DESKTOP | 1440 × 1024 | `node_16313415218959588513` | Management table of imported bank statements across commercial bank accounts. |
| 13 | **Bank Statements — Mobile** | MOBILE | 390 × 926 | `node_6639406781483311302` | Mobile card feed of recent statement imports. |
| 14 | **Statement Upload — Desktop** | DESKTOP | 1440 × 1024 | `node_8432169691970019648` | Drag-and-drop CSV / MT940 / CAMT.053 bank statement importer with live validation parsing table. |
| 15 | **Statement Upload — Mobile** | MOBILE | 390 × 884 | `node_9681286156971537152` | Mobile statement document capture and file selector. |
| 16 | **Ledger Imports — Desktop** | DESKTOP | 1440 × 1024 | `node_7759866963047076241` | ERP journal entry import log (NetSuite, SAP, QuickBooks) with double-entry balance verification. |
| 17 | **Ledger Imports — Mobile** | MOBILE | 390 × 884 | `node_5405783959126127971` | Mobile view of GL batch sync status. |
| 18 | **Reconciliation Workspace — Desktop** | DESKTOP | 1440 × 1024 | `node_1930337144009910989` | Split matching workbench: Left bank transactions vs. Right ledger entries with run engine controls. |
| 19 | **Reconciliation Workspace — Mobile** | MOBILE | 390 × 884 | `node_8000772499871484433` | Mobile swipeable card matching flow. |
| 20 | **Reconciliation Workspace — Tablet** | TABLET | 768 × 1024 | `node_10751044757763022192` | Tablet view of side-by-side reconciliation workspace. |
| 21 | **AI Matching Explanation — Desktop** | DESKTOP | 1280 × 1024 | `node_9945726542728411582` | AI proposal breakdown: semantic merchant similarity score, date window analysis, and rule provenance. |
| 22 | **AI Matching Explanation — Mobile** | MOBILE | 390 × 884 | `node_5944295854035567665` | Mobile compact AI match explanation sheet. |
| 23 | **Review Queue — Desktop** | DESKTOP | 1280 × 1024 | `node_9651375759358221504` | Prioritized queue table for unconfirmed matches requiring human-in-the-loop review. |
| 24 | **Review Queue — Mobile** | MOBILE | 390 × 884 | `node_15328032734650896414` | Mobile card-based exception review queue. |
| 25 | **Review Queue Redesign — Mobile** | MOBILE | 390 × 884 | `node_14747090970822557251` | Updated mobile review queue with quick one-tap approve / flag buttons. |
| 26 | **Transaction Details — Desktop** | DESKTOP | 1280 × 1298 | `node_14037088769769828014` | Deep audit drill-down for a single transaction: raw bank payload, matched GL entry, and audit history. |
| 27 | **Transaction Details — Mobile** | MOBILE | 390 × 884 | `node_13999642305557915058` | Mobile detail view for transaction audit properties. |
| 28 | **Audit Trail — Desktop** | DESKTOP | 1280 × 1024 | `node_8898001311391110947` | Immutable tamper-evident audit ledger with SHA-256 chain verification, actor log, and event details. |
| 29 | **Audit Trail — Mobile** | MOBILE | 390 × 884 | `node_3735628699460781380` | Mobile audit activity timeline. |
| 30 | **Integrations — Desktop** | DESKTOP | 1280 × 1024 | `node_3337784576918644636` | Real-time monitoring of simulated bank APIs & ERP webhooks: rate limits, retry counts, latency, and dead-letters. |
| 31 | **Integrations — Mobile** | MOBILE | 390 × 884 | `node_14037088769769827034` | Mobile integration status health cards. |
| 32 | **Reports — Desktop** | DESKTOP | 1280 × 1128 | `node_16701247961692749160` | Financial reporting analytics: daily/monthly reconciliation, bank fee analysis, multi-currency tables, CSV exports. |
| 33 | **Reports — Mobile** | MOBILE | 390 × 884 | `node_3849317510461659039` | Mobile financial summary metrics and monthly rates. |
| 34 | **Settings — Desktop** | DESKTOP | 1280 × 1024 | `node_555732654437551859` | Team member RBAC management, invitation status, organization settings, and security policy. |
| 35 | **Settings — Mobile** | MOBILE | 390 × 884 | `node_5642833421119916042` | Mobile organization profile and settings. |
| 36 | **User Profile — Desktop** | DESKTOP | 1280 × 1024 | `node_12633660118562072923` | Personal user settings, active session devices, and security credentials. |
| 37 | **User Profile — Mobile** | MOBILE | 390 × 884 | `node_17154075230169879911` | Mobile profile management. |
| 38 | **Notifications — Desktop** | DESKTOP | 1280 × 1024 | `node_3324476310123525484` | Notification center for approval requests, statement import alerts, and rule mismatch warnings. |
| 39 | **Notifications — Mobile** | MOBILE | 390 × 884 | `node_16597106574502003101` | Mobile push & system notifications view. |
| 40 | **Exception Management (Split Drawer)** | DESKTOP | 1280 × 1024 | `node_17891401107239667581` | Split-screen workbench featuring a dedicated right-hand drawer for immediate exception resolution. |
| 41 | **Approval Modal A — Side-by-Side** | COMPONENT | 620 × 506 | `node_17546121455393496883` | Standard match approval modal with side-by-side comparison of Bank Transaction vs. GL Entry. |
| 42 | **Approval Modal B — Deterministic Gate** | COMPONENT | 540 × 442 | `node_912486797798717112` | Strict gate modal highlighting field-by-field deltas (e.g. FX variance delta +$142.80) before posting. |
| 43 | **Approval Modal C — Exception Attestation** | COMPONENT | 580 × 369 | `node_16827939817932778490` | Maker-checker controller approval modal requiring attestation sign-off for out-of-policy exceptions. |
| 44 | **Bank vs Ledger — Mismatch Comparison** | COMPONENT | 960 × 523 | `node_14356017924881094705` | Detailed 3-column breakdown comparing Bank vs. Ledger with exact mismatch rule evidence. |
| 45 | **FinBridge — Operational Error States** | COMPONENT | 1080 × 1119 | `node_10058363155075047501` | Comprehensive UI error state catalog: rate limit 429, ERP timeout, network drops, and corrupted statements. |
| 46 | *(Untitled Node Canvas)* | CANVAS | — | `node_17178329002682352282` | Master canvas container holding project coordinate instances. |
| 47 | *(Mobile Integration Node)* | MOBILE | — | `node_14037088769769827034` | Sub-node instance for mobile integration diagnostics. |

---

## 15. Next Steps for Implementation

Once approved, this design system will be codified into the application via:
1. Updating `frontend/tailwind.config.js` to expose all official `midnight-navy`, `bridge-indigo`, `trust-emerald`, `surface-container-*`, and typography scales.
2. Aligning existing pages ([DashboardPage](file:///D:/Founding-Projects/FinBridge/frontend/src/pages/DashboardPage.tsx), [ReconciliationPage](file:///D:/Founding-Projects/FinBridge/frontend/src/pages/ReconciliationPage.tsx), [ReviewQueuePage](file:///D:/Founding-Projects/FinBridge/frontend/src/pages/ReviewQueuePage.tsx), [AuditTrailPage](file:///D:/Founding-Projects/FinBridge/frontend/src/pages/AuditTrailPage.tsx)) with the exact Stitch component structures.
3. Building the 3 dedicated approval modals (`ApprovalModalA`, `ApprovalModalB`, `ApprovalModalC`) and the `ExceptionManagementDrawer`.
