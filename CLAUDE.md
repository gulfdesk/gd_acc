# gd_acc

Frappe app for employee accommodation: entitlements, beds, allocations, transfers, maintenance. Desk UI only.

## UI Contract

1. **Frappe first.** Use Frappe's own UI: form fields, `add_custom_button`, list-view indicators, report formatters, `frappe.ui.Dialog`. Custom HTML only in an HTML field or a Desk page.
2. **Frappe classes in custom HTML.** Use `frappe-control`, `control-label`, `control-value like-disabled-input`, Bootstrap `row` / `col-sm-6`, `table table-bordered`, `indicator-pill`, `text-muted`. Use Frappe CSS variables (`--text-muted`, `--border-color`), never fixed colors.
3. **One status color.** Every status pill and list indicator reads `gd_acc.accommodation.STATUS_COLORS` through `status_color()` or `status_pill()` in `public/js/accommodation.bundle.js`. Add a new status there. Never write a local color map.
4. **Buttons.** Group related form buttons under one group label, for example `Accommodation`.
5. **Compact and readable.** Label and value pairs in 2 columns. Tables: one line per row, small text, sticky header, and at most 5 visible rows before the table scrolls. Show an empty value as blank.
6. **Same thing, same look.** Two tables or panels that show similar data use one shared render function.
7. **Plain text.** Short labels in Title Case. Wrap every user-visible string in `__()`. Escape data with `frappe.utils.escape_html`.
