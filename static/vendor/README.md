# Vendor JavaScript (self-hosted; pages never load a third-party CDN)
#
# | File              | Version | Source |
# |-------------------|---------|--------|
# | htmx.min.js       | 2.0.10  | https://unpkg.com/htmx.org@2.0.10/dist/htmx.min.js |
# |                   |         | upstream: https://github.com/bigskysoftware/htmx/releases/tag/v2.0.10 |
# | alpine.csp.min.js | 3.17.1  | https://unpkg.com/@alpinejs/csp@3.17.1/dist/cdn.min.js |
# |                   |         | npm: @alpinejs/csp (CSP-compatible build, no eval) |
# | Sortable.min.js   | 1.15.6  | https://unpkg.com/sortablejs@1.15.6/Sortable.min.js |
# |                   |         | upstream: https://github.com/SortableJS/Sortable/releases/tag/1.15.6 |
#
# SortableJS is for M6 scrim admin drag-and-drop. M0 does not load it on every page.
