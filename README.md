# replacement-filter-finder

Static site published with GitHub Pages from the `main` branch root:
https://wfsmith10.github.io/replacement-filter-finder/

- Edit pages in `content/*.html` (JSON metadata comment on the first line, then the body).
- Site config: `site.json`. Styles: `assets/style.css`.
- New page template: `templates/article-template.html`.
- Build and check links: `python3 build.py --check` (writes `index.html`, `<slug>/index.html`, `404.html`, `sitemap.xml`, `robots.txt` at the repo root). Commit the generated files.
- No dependencies, no analytics, no tracking.
