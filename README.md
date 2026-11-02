# Mapping Accessibility Project (MAP) registry

This repository is the single source of truth for MAP's public record of projects, and it builds MAP's public pages at <https://wwu-mapping-accessibility.github.io/>.

MAP is a collaboration at Western Washington University (WWU) in which students in ENVS 421 (GIS IV), senior projects and internships map barriers and resources for people with disabilities on campus and in Bellingham.

## What lives where

| Content | Home |
| --- | --- |
| One record per project (title, term, summary, links) | `projects/` in this repo |
| Public bios (only with consent) | `people.yml` |
| Literature and MAP's own citable outputs | [Zotero group "Mapping Accessibility"](https://www.zotero.org/groups/5222766/mapping_accessibility) |
| Live maps, layers, dashboards, forms | ArcGIS Online group [MAP Published](https://wwu.maps.arcgis.com/home/group.html?id=8af3a042c5ee44389f7c4195d3842a87), listed on the [Hub catalog](https://mapping-accessibility-wwu.hub.arcgis.com) |
| Reports, raw data, photos, audio | MAP SharePoint, `Projects/<id>/` |
| Code and tools | Repos in this GitHub organization |

The story of MAP is told on the WordPress site (wp.wwu.edu/accessiblemaps), which links here for projects, the library and data.

## Add or update a project

1. Copy `templates/project.yml` to `projects/<year>-<term>_<short-name>.yml`, for example `projects/2026-spring_automatic-doors.yml`.
2. Fill in the fields. Keep the summary to about 100 plain-language words.
3. Leave `status: draft`. Only the MAP coordinator changes it to `published`.
4. Open a pull request. Merging a pull request with `status: published` puts the project on the public site.

ENVS 421 teams do this as part of their final handoff. The full checklist is in `templates/handoff_checklist.md`.

## Rules

- **Names and photos** appear only when the people in them agreed at handoff (`names_public: true`). Until then, leave `team` empty: this repository is public.
- **License:** MAP data and reports are shared under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Code in `scripts/` is MIT licensed. See `LICENSE.md`.
- **Accessibility:** every map needs a text alternative and every image needs alt text. The build refuses an image without alt text.
- **Large files** (geodatabases, point clouds, audio) do not go in GitHub. Link to SharePoint or ArcGIS Online instead.

## How the build works

`scripts/build.py` reads `projects/*.yml`, checks each file, pulls the Zotero group through its public API, and writes:

- `_site/` — the public pages: Projects, Library, Data & Tools
- `_site/outputs/canvas_past_work.html` — paste or push into the Canvas "Past Work" page
- `_site/outputs/digest.md` — an announcement draft for Teams, Discord and email

A GitHub Action runs the build on every push and every night, and publishes `_site/` with GitHub Pages.

To preview locally, including drafts:

```
pip install pyyaml
python scripts/build.py --include-drafts
```

Then open `_site/index.html`.
