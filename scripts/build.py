#!/usr/bin/env python3
"""Build MAP's public pages from projects/*.yml and the Zotero group.

Usage:
    python scripts/build.py                  # published projects only (what the site shows)
    python scripts/build.py --include-drafts # preview everything, marked as drafts
    python scripts/build.py --no-zotero      # skip the network call (offline preview)

Writes _site/ (HTML pages + outputs/). Exits non-zero if any project file is invalid.
"""
import argparse
import datetime as dt
import html
import json
import pathlib
import shutil
import sys
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"
ZOTERO_GROUP = "5222766"
ZOTERO_URL = "https://www.zotero.org/groups/5222766/mapping_accessibility"
HUB_URL = "https://mapping-accessibility-wwu.hub.arcgis.com"
AGOL_GROUP = "https://wwu.maps.arcgis.com/home/group.html?id=8af3a042c5ee44389f7c4195d3842a87"
WORDPRESS_URL = "https://wp.wwu.edu/accessiblemaps/"
TRACKS = {"ENVS 421", "senior project", "internship", "research"}
LINK_LABELS = [
    ("storymap", "Story map"),
    ("text_version", "Text version of the story map"),
    ("webmap", "Web map"),
    ("dashboard", "Dashboard"),
    ("app", "Map app"),
    ("form", "Data-collection form"),
    ("report", "Report"),
    ("data", "Data"),
    ("code", "Code"),
]
TERM_ORDER = {"Winter": 1, "Spring": 2, "Summer": 3, "Fall": 4}

e = html.escape


# ---------------------------------------------------------------- projects
def load_projects(include_drafts):
    themes = yaml.safe_load((ROOT / "themes.yml").read_text())
    errors, projects = [], []
    for path in sorted((ROOT / "projects").glob("*.yml")):
        p = yaml.safe_load(path.read_text()) or {}
        where = path.name
        for field in ("id", "title", "term", "track", "theme", "summary", "status"):
            if not p.get(field):
                errors.append(f"{where}: missing {field}")
        if p.get("id") and p["id"] != path.stem:
            errors.append(f"{where}: id '{p['id']}' does not match the file name")
        if p.get("theme") and p["theme"] not in themes:
            errors.append(f"{where}: unknown theme '{p['theme']}' (see themes.yml)")
        for t in p.get("also_themes") or []:
            if t not in themes:
                errors.append(f"{where}: unknown theme '{t}' in also_themes")
        if p.get("track") and p["track"] not in TRACKS:
            errors.append(f"{where}: track must be one of {sorted(TRACKS)}")
        if p.get("status") not in ("draft", "published"):
            errors.append(f"{where}: status must be draft or published")
        if p.get("team") and not p.get("names_public"):
            errors.append(f"{where}: team names listed but names_public is not true")
        img = p.get("image") or {}
        if img.get("file") and not img.get("alt"):
            errors.append(f"{where}: image has no alt text")
        if p.get("status") == "published" or include_drafts:
            projects.append(p)
    projects.sort(key=sort_key, reverse=True)
    return themes, projects, errors


def sort_key(p):
    parts = str(p.get("term", "")).split()
    if len(parts) == 2 and parts[1].isdigit():
        return (int(parts[1]), TERM_ORDER.get(parts[0], 0))
    return (0, 0)


def is_url(s):
    return isinstance(s, str) and s.startswith(("http://", "https://"))


# ---------------------------------------------------------------- zotero
def zotero_get(path):
    url = f"https://api.zotero.org/groups/{ZOTERO_GROUP}/{path}"
    req = urllib.request.Request(url, headers={"Zotero-API-Version": "3"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode()), r.headers


def zotero_all(path):
    out, start = [], 0
    while True:
        sep = "&" if "?" in path else "?"
        batch, headers = zotero_get(f"{path}{sep}limit=100&start={start}")
        out.extend(batch)
        total = int(headers.get("Total-Results", len(out)))
        start += 100
        if start >= total or not batch:
            return out


def load_library():
    collections = zotero_all("collections")
    items = zotero_all("items/top?include=bib,data&style=apa&sort=creator")
    by_key = {c["key"]: c["data"] for c in collections}

    def top_name(key):
        seen = set()
        while key in by_key and by_key[key].get("parentCollection") and key not in seen:
            seen.add(key)
            key = by_key[key]["parentCollection"]
        return by_key.get(key, {}).get("name", "Other")

    groups = {}
    for it in items:
        if it["data"].get("itemType") in ("attachment", "note"):
            continue
        names = {top_name(k) for k in it["data"].get("collections", [])} or {"Not yet sorted"}
        for n in names:
            groups.setdefault(n, []).append(it)
    return groups, len(items)


# ---------------------------------------------------------------- html
CSS = """
:root{--bg:#fff;--fg:#1b1b1b;--muted:#4a4a4a;--line:#d0d0d0;--link:#0b4f8a;--accent:#003f87;--chip:#eef3f8;--draft:#7a4b00;--draftbg:#fff4e0}
@media (prefers-color-scheme:dark){:root{--bg:#121417;--fg:#f0f0f0;--muted:#c4c4c4;--line:#3a3f45;--link:#8cc4ff;--accent:#8cc4ff;--chip:#1f2a36;--draft:#ffd28a;--draftbg:#3a2c12}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:1.0625rem/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--link)} a:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.skip{position:absolute;left:-999px} .skip:focus{left:1rem;top:1rem;background:var(--bg);padding:.5rem;z-index:2}
header,main,footer{max-width:60rem;margin:0 auto;padding:0 1rem}
header{border-bottom:1px solid var(--line);padding-top:1rem;padding-bottom:.5rem}
header p{margin:0;font-weight:700;font-size:1.15rem}
nav ul{list-style:none;padding:0;margin:.5rem 0 0;display:flex;flex-wrap:wrap;gap:.25rem 1.25rem}
nav a[aria-current=page]{font-weight:700;text-decoration-thickness:3px}
h1{font-size:2rem;line-height:1.2} h2{margin-top:2.5rem;border-bottom:1px solid var(--line);padding-bottom:.25rem} h3{margin-bottom:.25rem}
.lead{font-size:1.15rem;color:var(--muted)}
.meta{color:var(--muted);margin:.25rem 0 .75rem}
.card{border:1px solid var(--line);border-radius:8px;padding:1rem 1.25rem;margin:1rem 0}
.card img{max-width:100%;height:auto;border-radius:6px}
.chips{list-style:none;padding:0;display:flex;flex-wrap:wrap;gap:.5rem}
.chips li{background:var(--chip);border-radius:999px;padding:.1rem .75rem}
.draft{background:var(--draftbg);color:var(--draft);border-radius:4px;padding:0 .4rem;font-weight:700;font-size:.9rem}
.bib{margin:.75rem 0;padding-left:1.5rem;text-indent:-1.5rem}
footer{border-top:1px solid var(--line);margin-top:3rem;padding-top:1rem;padding-bottom:2rem;color:var(--muted);font-size:.95rem}
"""

NAV = [("index.html", "Home"), ("projects.html", "Projects"), ("data.html", "Data and tools"), ("library.html", "Library")]


def page(fname, title, body, built):
    current = ' aria-current="page"'
    nav = "".join(
        f'<li><a href="{href}"{current if href == fname else ""}>{label}</a></li>'
        for href, label in NAV
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} | Mapping Accessibility Project</title>
<style>{CSS}</style>
</head>
<body>
<a class="skip" href="#main">Skip to main content</a>
<header>
<p>Mapping Accessibility Project (MAP)</p>
<nav aria-label="Main"><ul>{nav}<li><a href="{WORDPRESS_URL}">About MAP</a></li></ul></nav>
</header>
<main id="main">
{body}
</main>
<footer>
<p>Mapping Accessibility Project, Western Washington University. Content is shared under
<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. Updated {built}.</p>
<p>Found an accessibility problem with this page? Tell us at lasof@wwu.edu.</p>
</footer>
</body>
</html>
"""


def project_card(p, themes, heading="h3"):
    theme_names = [themes[p["theme"]]["name"]] + [themes[t]["name"] for t in p.get("also_themes") or []]
    draft = ' <span class="draft">Draft</span>' if p.get("status") != "published" else ""
    meta = f'{e(p["term"])} · {e(p["track"])}' + (f' · with {e(p["partner"])}' if p.get("partner") else "")
    parts = [f'<article class="card" id="{e(p["id"])}">', f'<{heading}>{e(p["title"])}{draft}</{heading}>', f'<p class="meta">{meta}</p>']
    img = p.get("image") or {}
    if img.get("file"):
        src = img["file"] if is_url(img["file"]) else f"images/{img['file']}"
        parts.append(f'<img src="{e(src)}" alt="{e(img["alt"])}" loading="lazy">')
    parts.append(f"<p>{e(str(p['summary']).strip())}</p>")
    if p.get("names_public") and p.get("team"):
        parts.append(f"<p><strong>Team:</strong> {e(', '.join(p['team']))}</p>")
    links = [(label, p["links"][k]) for k, label in LINK_LABELS if is_url((p.get("links") or {}).get(k))]
    if links:
        items = "".join(f'<li><a href="{e(u)}">{e(label)}<span class="skip">, {e(p["title"])}</span></a></li>' for label, u in links)
        parts.append(f'<ul class="chips" aria-label="Links for {e(p["title"])}">{items}</ul>')
    if p.get("next_steps"):
        parts.append(f"<p><strong>Next steps:</strong> {e(p['next_steps'])}</p>")
    parts.append(f'<p class="meta">Themes: {e(", ".join(theme_names))}</p>')
    parts.append("</article>")
    return "\n".join(parts)


def build_projects(themes, projects, built):
    if not projects:
        body = "<h1>Projects</h1><p class=\"lead\">Project pages are being reviewed and will appear here soon.</p>"
        return page("projects.html", "Projects", body, built)
    toc = "".join(f'<li><a href="#theme-{k}">{e(v["name"])}</a></li>' for k, v in themes.items() if any(p["theme"] == k for p in projects))
    body = [
        "<h1>Projects</h1>",
        f'<p class="lead">{len(projects)} projects by students in ENVS 421 (GIS IV), senior projects and internships, newest first within each theme.</p>',
        f'<nav aria-label="Themes"><ul class="chips">{toc}</ul></nav>',
    ]
    for k, v in themes.items():
        group = [p for p in projects if p["theme"] == k]
        if not group:
            continue
        body.append(f'<h2 id="theme-{k}">{e(v["name"])}</h2><p>{e(v["blurb"])}</p>')
        body.extend(project_card(p, themes) for p in group)
    return page("projects.html", "Projects", "\n".join(body), built)


def build_library(groups, total, built):
    if groups is None:
        body = f'<h1>Library</h1><p class="lead">The library could not be loaded this time. Browse it directly in the <a href="{ZOTERO_URL}/library">MAP Zotero group</a>.</p>'
        return page("library.html", "Library", body, built)
    order = sorted(groups, key=lambda n: (n != "MAP Outputs", n == "Not yet sorted", n.lower()))
    toc = "".join(f'<li><a href="#c{i}">{e(n)} ({len(groups[n])})</a></li>' for i, n in enumerate(order))
    body = [
        "<h1>Library</h1>",
        f'<p class="lead">{total} sources collected by MAP students and faculty, from disability studies to accessible map design. '
        f'This page is rebuilt every night from the <a href="{ZOTERO_URL}/library">MAP Zotero group</a>, where you can search, export citations and see notes.</p>',
        f'<nav aria-label="Collections"><ul>{toc}</ul></nav>',
    ]
    for i, n in enumerate(order):
        body.append(f'<h2 id="c{i}">{e(n)}</h2>')
        for it in sorted(groups[n], key=lambda x: x.get("bib", "")):
            body.append(f'<div class="bib">{it.get("bib", "")}</div>')  # Zotero returns sanitized citation HTML
    return page("library.html", "Library", "\n".join(body), built)


def build_data(built):
    body = f"""<h1>Data and tools</h1>
<p class="lead">Maps, datasets, survey forms and code made by MAP students, free to reuse under CC BY 4.0.</p>
<h2>Maps and datasets</h2>
<p>Every published map, layer, dashboard and survey form is in the <a href="{HUB_URL}">MAP data catalog</a>, where you can search, preview and download data as CSV, GeoJSON or shapefile. The same items are listed in the <a href="{AGOL_GROUP}">MAP Published group</a> in ArcGIS Online.</p>
<h2>Code</h2>
<p>Scripts and tools, such as the ADA route builder for Arntzen Hall, are in the <a href="https://github.com/WWU-Mapping-Accessibility">WWU-Mapping-Accessibility GitHub organization</a>.</p>
<h2>Reports and raw data</h2>
<p>Each <a href="projects.html">project</a> links to its report and data. Some files are stored in WWU's SharePoint; if a link asks you to sign in, email lasof@wwu.edu for a copy.</p>
"""
    return page("data.html", "Data and tools", body, built)


def build_index(themes, projects, n_sources, built):
    recent = projects[:3]
    cards = "\n".join(project_card(p, themes, heading="h3") for p in recent)
    body = f"""<h1>Mapping Accessibility Project</h1>
<p class="lead">Students at Western Washington University map the barriers and resources that shape who can move through campus and Bellingham, and share the data so others can act on it.</p>
<ul>
<li><a href="projects.html">Projects</a>: {len(projects)} student projects since 2023</li>
<li><a href="data.html">Data and tools</a>: maps, datasets, survey forms and code</li>
<li><a href="library.html">Library</a>: {n_sources if n_sources else "MAP's"} sources on disability, access and mapping</li>
<li><a href="{WORDPRESS_URL}">About MAP</a>: our story and how to get involved</li>
</ul>
{"<h2>Recent projects</h2>" + cards if recent else ""}
"""
    return page("index.html", "Home", body, built)


# ---------------------------------------------------------------- outputs
def canvas_past_work(themes, projects):
    out = ["<p>Past MAP projects by ENVS 421 students, newest first. Each project lists its maps, report and data. "
           f'Browse everything in the <a href="{HUB_URL}">MAP data catalog</a> and the <a href="{ZOTERO_URL}/library">MAP library</a>.</p>']
    for p in [p for p in projects if p["track"] == "ENVS 421"]:
        out.append(f"<h3>{e(p['term'])}: {e(p['title'])}</h3>")
        out.append(f"<p>{e(str(p['summary']).strip())}</p>")
        links = [(label, p["links"][k]) for k, label in LINK_LABELS if is_url((p.get("links") or {}).get(k))]
        if links:
            out.append("<ul>" + "".join(f'<li><a href="{e(u)}">{e(label)}</a></li>' for label, u in links) + "</ul>")
        if p.get("next_steps"):
            out.append(f"<p><strong>Next steps for future teams:</strong> {e(p['next_steps'])}</p>")
    return "\n".join(out)


def digest(projects, built):
    lines = [f"# MAP update, {built}", ""]
    for p in projects[:6]:
        lines += [f"**{p['title']}** ({p['term']}, {p['track']})", str(p["summary"]).strip(), ""]
    lines.append("All projects: https://wwu-mapping-accessibility.github.io/projects.html")
    return "\n".join(lines)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-drafts", action="store_true")
    ap.add_argument("--no-zotero", action="store_true")
    args = ap.parse_args()

    themes, projects, errors = load_projects(args.include_drafts)
    if errors:
        print("Project files need fixing:", *errors, sep="\n  ", file=sys.stderr)
        sys.exit(1)

    groups, total = (None, 0)
    if not args.no_zotero:
        try:
            groups, total = load_library()
        except Exception as exc:  # keep the rest of the site building if Zotero is down
            print(f"Warning: Zotero not loaded ({exc})", file=sys.stderr)

    built = dt.date.today().isoformat()
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "outputs").mkdir(parents=True)
    if (ROOT / "images").exists():
        shutil.copytree(ROOT / "images", OUT / "images")
    (OUT / "index.html").write_text(build_index(themes, projects, total, built))
    (OUT / "projects.html").write_text(build_projects(themes, projects, built))
    (OUT / "library.html").write_text(build_library(groups, total, built))
    (OUT / "data.html").write_text(build_data(built))
    (OUT / "outputs" / "canvas_past_work.html").write_text(canvas_past_work(themes, projects))
    (OUT / "outputs" / "digest.md").write_text(digest(projects, built))
    (OUT / ".nojekyll").write_text("")
    print(f"Built {len(projects)} projects, {total} library sources -> {OUT}")


if __name__ == "__main__":
    main()
