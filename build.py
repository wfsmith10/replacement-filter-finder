#!/usr/bin/env python3
"""Tiny static site generator (no dependencies).

Source:  site.json            site-wide config
         content/<slug>.html  one file per page. First line is an HTML comment
                              holding JSON metadata, the rest is the page body.
Output:  index.html (slug "index"), <slug>/index.html, 404.html,
         sitemap.xml, robots.txt  (written at the repo root for GitHub Pages)

Page metadata keys:
  title (required), description (required), h1, nav_label,
  affiliate (bool; true => disclosure banner rendered at top of page),
  schema_type (WebPage | CollectionPage | AboutPage | ContactPage | Article),
  parent (slug of parent page for breadcrumbs), updated (YYYY-MM-DD),
  sitemap (bool, default true), noindex (bool)

In page bodies write internal links as  href="{{base}}/slug/"  (or "{{base}}/" for home).
Affiliate links must use rel="sponsored nofollow" and the page must set "affiliate": true.

Run:  python3 build.py           build
      python3 build.py --check   build, then check all internal links + rules (non-zero exit on error)
"""
import html, json, os, re, sys, datetime, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
CFG = json.loads((ROOT / "site.json").read_text())
BASE = CFG["base_path"].rstrip("/")          # e.g. "/replacement-filter-finder"
ORIGIN = CFG["origin"].rstrip("/")           # e.g. "https://wfsmith10.github.io"
SITE_URL = ORIGIN + BASE + "/"
TODAY = datetime.date.today().isoformat()

CF_BEACON = '<!-- Cloudflare Web Analytics --><script type=\'module\' src=\'https://static.cloudflareinsights.com/beacon.min.js\' data-cf-beacon=\'{"token": "2ed8f27f3bfb4315b0222714e84995ff"}\'></script><!-- End Cloudflare Web Analytics -->'


def load_pages():
    pages = {}
    for f in sorted((ROOT / "content").glob("*.html")):
        raw = f.read_text()
        m = re.match(r"\s*<!--(.*?)-->\s*", raw, re.S)
        if not m:
            sys.exit(f"ERROR {f.name}: missing JSON metadata comment on first line")
        meta = json.loads(m.group(1))
        for k in ("title", "description"):
            if not meta.get(k):
                sys.exit(f"ERROR {f.name}: metadata '{k}' is required")
        meta["slug"] = f.stem
        meta["body"] = re.sub(r"<!--.*?-->", "", raw[m.end():], flags=re.S)  # strip author comments
        pages[f.stem] = meta
    if "index" not in pages:
        sys.exit("ERROR: content/index.html (home page) is required")
    return pages


def url_path(slug):
    return f"{BASE}/" if slug == "index" else f"{BASE}/{slug}/"


def abs_url(slug):
    return ORIGIN + url_path(slug)


def out_file(slug):
    return ROOT / ("index.html" if slug == "index" else f"{slug}/index.html")


def breadcrumbs(page, pages):
    chain, cur, seen = [], page, set()
    while cur and cur["slug"] not in seen:
        seen.add(cur["slug"])
        chain.insert(0, cur)
        cur = pages.get(cur.get("parent") or ("index" if cur["slug"] != "index" else None))
    return chain


def render(page, pages):
    e = html.escape
    slug = page["slug"]
    body = page["body"].replace("{{base}}", BASE).replace("{{email}}", CFG["contact_email"])
    crumbs = breadcrumbs(page, pages)
    graph = []
    if slug == "index":
        graph.append({"@type": "WebSite", "@id": SITE_URL + "#website", "name": CFG["name"],
                      "url": SITE_URL, "description": CFG["tagline"], "inLanguage": "en-US",
                      "publisher": {"@id": SITE_URL + "#org"}})
        graph.append({"@type": "Organization", "@id": SITE_URL + "#org", "name": CFG["name"],
                      "url": SITE_URL, "email": CFG["contact_email"]})
    wp = {"@type": page.get("schema_type", "WebPage"), "@id": abs_url(slug) + "#webpage",
          "url": abs_url(slug), "name": page["title"], "description": page["description"],
          "isPartOf": {"@id": SITE_URL + "#website"}, "inLanguage": "en-US",
          "dateModified": page.get("updated", TODAY)}
    if page.get("schema_type") == "Article":
        wp["headline"] = page.get("h1", page["title"])
        wp["author"] = {"@type": "Person", "name": CFG["author"]}
    graph.append(wp)
    if len(crumbs) > 1:
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": c.get("nav_label", c["title"]),
             "item": abs_url(c["slug"])} for i, c in enumerate(crumbs)]})
    jsonld = json.dumps({"@context": "https://schema.org", "@graph": graph}, indent=1)

    nav = "".join(
        f'<a href="{url_path(s)}"{" aria-current=\"page\"" if s == slug else ""}>{e(pages[s].get("nav_label", pages[s]["title"]))}</a>'
        for s in CFG["nav"] if s in pages)
    foot = " · ".join(f'<a href="{url_path(s)}">{e(pages[s].get("nav_label", pages[s]["title"]))}</a>'
                      for s in CFG["footer"] if s in pages)
    crumb_html = ""
    if len(crumbs) > 1:
        parts = [f'<a href="{url_path(c["slug"])}">{e(c.get("nav_label", c["title"]))}</a>' for c in crumbs[:-1]]
        parts.append(f'<span aria-current="page">{e(crumbs[-1].get("nav_label", crumbs[-1]["title"]))}</span>')
        crumb_html = '<nav class="crumbs" aria-label="Breadcrumb">' + " › ".join(parts) + "</nav>"
    banner = ""
    if page.get("affiliate"):
        banner = (f'<aside class="disclosure" role="note"><strong>Affiliate disclosure:</strong> '
                  f'{e(CFG["disclosure_short"])} <a href="{url_path("affiliate-disclosure")}">How we make money</a>.</aside>')
    robots = '<meta name="robots" content="noindex">' if page.get("noindex") else ""
    updated = page.get("updated")
    upd_html = f'<p class="updated">Last updated: <time datetime="{updated}">{updated}</time></p>' if updated and slug != "index" else ""
    if page.get("schema_type") == "Article" and updated:
        # Real editorial ownership (matches the About page): named editor + AI-assistance note + date.
        upd_html = (f'<p class="byline">Edited by {e(CFG["author"])} · researched with AI assistance · '
                    f'Last updated <time datetime="{updated}">{updated}</time> · '
                    f'<a href="{url_path("about")}">How we make pages</a></p>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(page["title"])}</title>
<meta name="description" content="{e(page["description"])}">
<meta name="google-site-verification" content="cwg7mBj5bSX5ovdlhtgpV2a0am_npVT5KAARmW5twY8">
{robots or f'<link rel="canonical" href="{abs_url(slug)}">'}
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(CFG["name"])}">
<meta property="og:title" content="{e(page["title"])}">
<meta property="og:description" content="{e(page["description"])}">
{"" if robots else f'<meta property="og:url" content="{abs_url(slug)}">'}
<link rel="icon" href="{BASE}/assets/favicon.svg" type="image/svg+xml">
<meta name="theme-color" content="{CFG.get("theme_color", "#ffffff")}">
<link rel="stylesheet" href="{BASE}/assets/style.css">
<script type="application/ld+json">
{jsonld}
</script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header"><div class="wrap">
<a class="brand" href="{BASE}/"><img class="mark" src="{BASE}/assets/favicon.svg" alt="" width="28" height="28">{e(CFG["name"])}</a>
<nav class="site-nav" aria-label="Main">{nav}</nav>
</div></header>
<main id="main" class="wrap">
{banner}
{crumb_html}
<h1>{e(page.get("h1", page["title"]))}</h1>
{upd_html}
{body}
</main>
<footer class="site-footer"><div class="wrap">
<p>{foot}</p>
<p>{e(CFG["footer_note"])}</p>
<p>Run by {e(CFG["author"])}. Pages are researched with AI assistance and checked against the sources they cite. <a href="{url_path("about")}">How we make pages</a>.</p>
<p>© {datetime.date.today().year} {e(CFG["name"])} · <a href="mailto:{CFG["contact_email"]}">{CFG["contact_email"]}</a></p>
</div></footer>
{CF_BEACON}
</body>
</html>
"""


def build():
    pages = load_pages()
    for p in pages.values():
        f = out_file(p["slug"])
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(render(p, pages))
    nf = {"slug": "404", "title": f"Page not found | {CFG['name']}", "nav_label": "Not found",
          "description": "The page you were looking for does not exist.", "noindex": True,
          "body": f'<p>That page does not exist (yet). Try the <a href="{BASE}/">home page</a>.</p>'}
    (ROOT / "404.html").write_text(render(nf, {**pages, "404": nf}))
    urls = "".join(
        f"<url><loc>{abs_url(s)}</loc><lastmod>{p.get('updated', TODAY)}</lastmod></url>\n"
        for s, p in pages.items() if p.get("sitemap", True) and not p.get("noindex"))
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n")
    print(f"Built {len(pages)} pages + 404, sitemap.xml, robots.txt -> {SITE_URL}")
    return pages


def check(pages):
    """Offline check: every internal href/src resolves to a built file; content rules."""
    errors = []
    for f in [out_file(s) for s in pages] + [ROOT / "404.html"]:
        txt = f.read_text()
        for ref in re.findall(r'(?:href|src)="([^"]+)"', txt):
            if ref.startswith(("http://", "https://", "mailto:", "#")):
                if ref.startswith(ORIGIN + BASE):
                    ref = ref[len(ORIGIN):]
                else:
                    continue
            ref = ref.split("#")[0].split("?")[0]
            if not ref.startswith(BASE + "/") and ref != BASE + "/":
                errors.append(f"{f.relative_to(ROOT)}: link outside site base: {ref}")
                continue
            rel = ref[len(BASE) + 1:]
            target = ROOT / rel
            if ref.endswith("/"):
                target = target / "index.html"
            if not target.exists():
                errors.append(f"{f.relative_to(ROOT)}: broken internal link {ref}")
    for s, p in pages.items():
        b = p["body"]
        if 'rel="sponsored' in b and not p.get("affiliate"):
            errors.append(f"content/{s}.html: has sponsored links but 'affiliate' is not true (disclosure banner missing)")
        if p.get("schema_type") == "Article":
            n = len(set(re.findall(r'href="\{\{base\}\}/([^"#]*)', b)))
            if n < 2:
                errors.append(f"content/{s}.html: article must link to >=2 existing pages (found {n})")
    for e_ in errors:
        print("ERROR", e_)
    print(f"Link/rule check: {len(errors)} error(s)")
    return not errors


if __name__ == "__main__":
    pages = build()
    if "--check" in sys.argv and not check(pages):
        sys.exit(1)
