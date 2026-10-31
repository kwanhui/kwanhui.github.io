# build/

`build_publications.py` generates `publications.html` from the lab's BibTeX file. The page is a build output: change the BibTeX records and rebuild rather than editing the HTML.

## Inputs

The script needs a BibTeX file and can take an optional status map. Each is looked up in this order:

| Input | Flag | Environment variable | `build/config.local.json` key |
|---|---|---|---|
| BibTeX file (required) | `--bib PATH` | `LAB_BIB` | `"bib"` |
| Status map (optional) | `--repo-map PATH` | `LAB_REPO_MAP` | `"repo_map"` |
| `validate_bib.py` (entry splitter) | `--parser PATH` | `LAB_BIB_PARSER` | `"parser"` |

`config.local.json` is a small local file, for example:

```json
{"bib": "/path/to/publications.bib", "repo_map": "/path/to/status-map.yaml"}
```

It is machine-specific and is not committed. If no parser path is given, the script looks for `scripts/validate_bib.py` one level above the folder that holds the BibTeX file and uses its `parse_bib_entries()` to split entries; field values are then read with a brace-aware parser so protected words such as `{LLM}` survive.

The status map is a YAML file with a `repos:` mapping whose entries carry `status`. When an entry's `note` contains a `Repo: <name>` token, that name is looked up there. Without a status map this check is skipped with a warning.

## Usage

Run from the repo root. Exactly one mode is required:

```bash
python3 build/build_publications.py --write              # regenerate publications.html
python3 build/build_publications.py --check              # compare with the committed page
python3 build/build_publications.py --out /tmp/pub.html  # write the rendering elsewhere for review
```

`--check` renders the page in memory and exits 1 with a short unified-diff summary when the committed `publications.html` differs, and 0 when it is up to date. It writes nothing, so it can run in any audit or pre-commit step to detect a stale page.

## What gets listed

- An entry is listed if and only if it has a `pdf` field naming a file in `publications/`.
- Years run newest first. Within a year, entries are ordered by `month` (`{jan}` to `{dec}`, latest first; entries without a month come last), then by key.
- Each line reads `Authors. <a href="./publications/FILE">Title</a>. Venue[, Vol. V, No. N][, Track][, pp. Pages | Article N]. Mon YYYY.` The venue is `booktitle` or `journal` (or `publisher`/`school` when neither exists). The optional `track` field (for example "Demonstration Track" or a workshop name) is printed after the venue. For an `@article`, the optional `articleno` field is printed as `Article N` in place of the page range; a `pages` value without a dash is treated the same way. Protective braces are removed, `--` becomes an en dash, `---` an em dash, LaTeX accents become Unicode, and the text is HTML-escaped.
- The page head, navigation, disclaimer and footer come from `templates/publications.html.j2`; only the year blocks are generated.

## Gates

The script prints every problem, exits 1 and writes nothing when:

- an entry's `pdf` file does not exist in `publications/`;
- two entries name the same `pdf`;
- an entry's `note` says "in preparation", "under review", "submitted" or "revision" (any case) and does not also say "accepted", "published", "camera-ready" or "available online";
- an entry's `note` has a `Repo: <name>` token and the status map gives that name a status other than `accepted` or `published`, or does not contain it;
- `month` is not a three-letter month, or `author`, `title` or `year` is missing.

It warns (and still exits 0) about PDFs in `publications/` that no entry references. Files listed in `unlisted-pdfs.txt` are kept on purpose and are not reported.

## Requirements

Python 3 with `jinja2`, and `PyYAML` when a status map is used.
