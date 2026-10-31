# kwanhui.github.io

The public website of the Social and Urban Analytics Lab, live at https://kwanhui.github.io/.

## How it is served

GitHub Pages serves the `master` branch root as plain static HTML (Bootstrap) using the branch build. There is no Jekyll and no GitHub Actions workflow; `.nojekyll` is present so Pages serves every file as-is. What is committed is exactly what is published.

## Folder map

| Path | What it is |
|------|------------|
| `index.html` | Front page: the lab, its research themes, contact. Hand-edited. |
| `people.html` | Lab members. Hand-edited. |
| `openings.html` | Open positions. Hand-edited. |
| `publications.html` | Publication list. **Generated** by `build/build_publications.py` from the lab's BibTeX records; never hand-edit. |
| `navbar.html`, `footer.html` | Shared navbar and footer, included into each page by `js/w3data.js` (`w3-include-html`). |
| `css/`, `js/`, `img/` | Stylesheets, scripts (Bootstrap, jQuery, w3data, `main.js`) and images. |
| `publications/` | Paper PDFs, named `YYYY-Venue-camelTopic.pdf`. Plain files, never Git LFS. |
| `build/` | The publications generator and its template. See `build/README.md`. |
| `ResearchStatement-KHLim-2025general.pdf`, `TeachingStatement-KHLim-2025general.pdf`, `ServiceStatement-KHLim-2025general.pdf` | The three statement PDFs. |

## Updating the publication list

1. Add or complete the entry in the lab's BibTeX records, with `doi`, `pdf` (`YYYY-Venue-camelTopic.pdf`) and `month`, and check it against the DOI metadata.
2. Copy the final PDF into `publications/` under the `pdf` filename.
3. Run `python3 build/build_publications.py --write` and review the diff of `publications.html`.
4. Commit, then push once the maintainer has approved that push.

`python3 build/build_publications.py --check` exits non-zero when `publications.html` is stale relative to the records.

## Content rules

This site is public, and anything pushed is visible immediately.

- Published or accepted work only. Nothing under review or in preparation.
- No submission or review status, and no funding amounts unless the funder has published them.
- People appear with their consent and are removed on request.
- Repository settings (visibility, Pages configuration, branches, analytics) are not changed by tooling, and no secrets or new third-party scripts are added.
- Every push is approved by the maintainer; approval does not carry over.
