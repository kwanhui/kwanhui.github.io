#!/usr/bin/env python3
"""Generate publications.html from a BibTeX file.

An entry is listed if and only if it has a `pdf` field naming a file in
publications/. Entries are grouped by year (newest first) and ordered within a
year by `month` (latest first; entries without a month come last), then by key.

Inputs (first match wins):
  bib file:    --bib, then $LAB_BIB, then "bib" in build/config.local.json
  status map:  --repo-map, then $LAB_REPO_MAP, then "repo_map" in build/config.local.json
               (optional: a YAML file with a `repos:` mapping whose entries carry `status`)

The BibTeX entry splitter is `parse_bib_entries` from the `validate_bib.py`
module that sits in `scripts/` beside the bib file's folder (or the path given
by --parser / $LAB_BIB_PARSER / "parser" in the config). Field values are then
re-read with a brace-aware parser so that protected words such as {LLM} survive.

Usage (exactly one mode):
  python3 build/build_publications.py --write        # regenerate publications.html
  python3 build/build_publications.py --check        # exit 1 if publications.html is stale
  python3 build/build_publications.py --out FILE     # write the rendering elsewhere for review
"""

import argparse
import difflib
import html
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

BUILD_DIR = Path(__file__).resolve().parent
REPO_DIR = BUILD_DIR.parent
PAGE = REPO_DIR / "publications.html"
PDF_DIR = REPO_DIR / "publications"
TEMPLATE_DIR = BUILD_DIR / "templates"
TEMPLATE_NAME = "publications.html.j2"
UNLISTED = BUILD_DIR / "unlisted-pdfs.txt"
LOCAL_CONFIG = BUILD_DIR / "config.local.json"

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun",
          "jul", "aug", "sep", "oct", "nov", "dec"]
MONTH_NAMES = {m: m.capitalize() for m in MONTHS}

BLOCKING_STATUS = re.compile(r"in preparation|under review|submitted|revision", re.I)
CLEARING_STATUS = re.compile(r"accepted|published|camera-ready|available online", re.I)
REPO_TOKEN = re.compile(r"\bRepo:\s*([A-Za-z0-9._-]+)")
OK_STATUSES = {"accepted", "published"}


# --------------------------------------------------------------------------- inputs

def load_config():
    if LOCAL_CONFIG.exists():
        try:
            return json.loads(LOCAL_CONFIG.read_text())
        except json.JSONDecodeError as e:
            sys.exit(f"error: {LOCAL_CONFIG.name} is not valid JSON ({e})")
    return {}


def resolve(cli_value, env_name, config, config_key):
    if cli_value:
        return Path(cli_value).expanduser()
    if os.environ.get(env_name):
        return Path(os.environ[env_name]).expanduser()
    if config.get(config_key):
        return Path(config[config_key]).expanduser()
    return None


def load_parser(parser_path, bib_path):
    candidates = [parser_path] if parser_path else []
    candidates.append(bib_path.resolve().parent.parent / "scripts" / "validate_bib.py")
    for path in candidates:
        if path and path.exists():
            spec = importlib.util.spec_from_file_location("validate_bib", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.parse_bib_entries
    sys.exit("error: cannot find validate_bib.py (pass --parser, set $LAB_BIB_PARSER, "
             "or add \"parser\" to build/config.local.json)")


def read_fields(raw):
    """Brace-balanced field reader: name = {value with {nested} braces}."""
    fields = {}
    for m in re.finditer(r"(\w+)\s*=\s*\{", raw):
        start = m.end()
        depth, j = 1, start
        while depth and j < len(raw):
            if raw[j] == "{":
                depth += 1
            elif raw[j] == "}":
                depth -= 1
            j += 1
        fields.setdefault(m.group(1).lower(), raw[start:j - 1].strip())
    return fields


def load_status_map(path):
    if path is None:
        return None
    try:
        import yaml
    except ImportError:
        sys.exit("error: PyYAML is needed to read the status map")
    data = yaml.safe_load(path.read_text()) or {}
    repos = data.get("repos") or {}
    return {name: (info or {}).get("status") for name, info in repos.items()}


# --------------------------------------------------------------------------- text

ACCENTS = {
    "'": "\u0301", "`": "\u0300", '"': "\u0308", "^": "\u0302", "~": "\u0303",
    "=": "\u0304", ".": "\u0307", "c": "\u0327", "v": "\u030c", "u": "\u0306",
    "H": "\u030b", "k": "\u0328",
}
SPECIAL = {r"\ss": "ß", r"\o": "ø", r"\O": "Ø", r"\aa": "å", r"\AA": "Å",
           r"\ae": "æ", r"\AE": "Æ", r"\l": "ł", r"\L": "Ł", r"\i": "ı"}


def latex_to_text(s):
    import unicodedata

    def accent(m):
        return unicodedata.normalize("NFC", m.group(2) + ACCENTS[m.group(1)])

    # \'{e}, \'e, {\'e}, \c{c}, \c c
    s = re.sub(r"\{\\([`'\"^~=.])\s*\{?([A-Za-z])\}?\}", accent, s)
    s = re.sub(r"\\([`'\"^~=.])\s*\{?([A-Za-z])\}?", accent, s)
    s = re.sub(r"\{\\([cvuHk])\s*\{?([A-Za-z])\}?\}", accent, s)
    s = re.sub(r"\\([cvuHk])(?:\{([A-Za-z])\}|\s+([A-Za-z]))",
               lambda m: unicodedata.normalize("NFC", (m.group(2) or m.group(3)) + ACCENTS[m.group(1)]), s)
    for cmd, ch in SPECIAL.items():
        s = re.sub(r"\{?" + re.escape(cmd) + r"(?![A-Za-z])\}?\s?", ch, s)
    s = s.replace("\\&", "&").replace("\\%", "%").replace("\\_", "_").replace("\\$", "$")
    s = s.replace("---", "\u2014").replace("--", "\u2013")
    s = s.replace("~", " ")
    s = s.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", s).strip()


def esc(s):
    return html.escape(latex_to_text(s), quote=False)


def format_authors(field):
    names = []
    for name in re.split(r"\s+and\s+", field.strip()):
        if "," in name:
            last, first = name.split(",", 1)
            name = f"{first.strip()} {last.strip()}"
        names.append(esc(name))
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def format_entry(entry):
    f = entry["fields"]
    parts = [format_authors(f["author"]),
             f'<a href="./publications/{html.escape(f["pdf"])}">{esc(f["title"])}</a>']
    venue = f.get("booktitle") or f.get("journal") or f.get("publisher") or f.get("school") or ""
    venue = esc(venue)
    is_article = entry["type"] == "article"
    if f.get("volume"):
        if is_article:
            venue += f", Vol. {esc(f['volume'])}" + (f", No. {esc(f['number'])}" if f.get("number") else "")
        elif f.get("series"):
            venue += f", {esc(f['series'])} {esc(f['volume'])}"
        else:
            venue += f", Vol. {esc(f['volume'])}"
    if f.get("track"):
        venue += f", {esc(f['track'])}"
    article_no = f.get("articleno") or (f.get("pages") if is_article and f.get("pages")
                                       and not re.search(r"[-\u2013:]", f["pages"]) else "")
    if is_article and article_no:
        venue += f", Article {esc(article_no)}"
    elif f.get("pages"):
        venue += f", pp. {esc(f['pages'])}"
    if venue:
        parts.append(venue)
    year = f["year"]
    month = MONTH_NAMES.get(f.get("month", "").lower())
    parts.append(f"{month} {year}" if month else year)
    return ". ".join(p.rstrip(".") for p in parts) + "."


def sort_key(entry):
    f = entry["fields"]
    month = f.get("month", "").lower()
    mrank = MONTHS.index(month) if month in MONTHS else -1
    return (-int(f["year"]), -mrank, entry["key"])


# --------------------------------------------------------------------------- gates

def check_gates(entries, status_map):
    problems = []
    seen = {}
    for e in entries:
        f, key = e["fields"], e["key"]
        pdf = f["pdf"]
        if not (PDF_DIR / pdf).is_file():
            problems.append(f"{key}: pdf file publications/{pdf} does not exist")
        if pdf in seen:
            problems.append(f"{key}: pdf {pdf} is also used by {seen[pdf]}")
        seen[pdf] = key
        for req in ("author", "title", "year"):
            if not f.get(req):
                problems.append(f"{key}: missing {req}")
        if f.get("year") and not re.fullmatch(r"\d{4}", f["year"]):
            problems.append(f"{key}: year '{f['year']}' is not a four-digit year")
        if f.get("month") and f["month"].lower() not in MONTHS:
            problems.append(f"{key}: month '{f['month']}' is not a three-letter month (jan..dec)")
        note = f.get("note", "")
        if BLOCKING_STATUS.search(note) and not CLEARING_STATUS.search(note):
            problems.append(f"{key}: note says the work is not yet accepted: {note!r}")
        m = REPO_TOKEN.search(note)
        if m and status_map is not None:
            name = m.group(1)
            status = status_map.get(name)
            if status is None:
                problems.append(f"{key}: 'Repo: {name}' is not in the status map")
            elif status not in OK_STATUSES:
                problems.append(f"{key}: status map gives '{status}' for {name} "
                                f"(must be one of {sorted(OK_STATUSES)})")
    return problems


def unreferenced_pdfs(entries):
    listed = {e["fields"]["pdf"] for e in entries}
    allowed = set()
    if UNLISTED.exists():
        allowed = {ln.strip() for ln in UNLISTED.read_text().splitlines()
                   if ln.strip() and not ln.lstrip().startswith("#")}
    return sorted(p.name for p in PDF_DIR.glob("*.pdf")
                  if p.name not in listed and p.name not in allowed)


# --------------------------------------------------------------------------- render

def render(entries):
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False,
                      trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
    years = []
    for e in sorted(entries, key=sort_key):
        y = e["fields"]["year"]
        if not years or years[-1][0] != y:
            years.append((y, []))
        years[-1][1].append(format_entry(e))
    return env.get_template(TEMPLATE_NAME).render(years=years)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="regenerate publications.html")
    mode.add_argument("--check", action="store_true",
                      help="exit 1 if publications.html differs from a fresh rendering")
    mode.add_argument("--out", metavar="PATH", help="write the rendering to PATH")
    ap.add_argument("--bib", help="BibTeX file (or $LAB_BIB, or config.local.json 'bib')")
    ap.add_argument("--repo-map", help="optional status map YAML (or $LAB_REPO_MAP, "
                                       "or config.local.json 'repo_map')")
    ap.add_argument("--parser", help="path to validate_bib.py (or $LAB_BIB_PARSER, "
                                     "or config.local.json 'parser')")
    args = ap.parse_args()

    config = load_config()
    bib = resolve(args.bib, "LAB_BIB", config, "bib")
    if bib is None:
        sys.exit("error: no bib file given (use --bib, $LAB_BIB or build/config.local.json)")
    if not bib.is_file():
        sys.exit(f"error: bib file not found: {bib}")
    status_path = resolve(args.repo_map, "LAB_REPO_MAP", config, "repo_map")
    if status_path is not None and not status_path.is_file():
        sys.exit(f"error: status map not found: {status_path}")
    parser_path = resolve(args.parser, "LAB_BIB_PARSER", config, "parser")

    parse_bib_entries = load_parser(parser_path, bib)
    entries = []
    for e in parse_bib_entries(bib.read_text()):
        fields = read_fields(e["raw"])
        if fields.get("pdf"):
            entries.append({"type": e["type"], "key": e["key"], "fields": fields})

    status_map = load_status_map(status_path)
    if status_map is None:
        print("warning: no status map given; the 'Repo:' status gate was skipped")

    problems = check_gates(entries, status_map)
    if problems:
        print(f"{len(problems)} problem(s); nothing written:")
        for p in problems:
            print(f"  - {p}")
        return 1

    for name in unreferenced_pdfs(entries):
        print(f"warning: publications/{name} is not referenced by any entry "
              f"(add it to build/unlisted-pdfs.txt if that is intended)")

    page = render(entries)
    if args.write:
        PAGE.write_text(page)
        print(f"wrote {PAGE.name}: {len(entries)} entries")
    elif args.out:
        Path(args.out).write_text(page)
        print(f"wrote {args.out}: {len(entries)} entries")
    else:
        current = PAGE.read_text() if PAGE.exists() else ""
        if current == page:
            print(f"{PAGE.name} is up to date ({len(entries)} entries)")
            return 0
        diff = list(difflib.unified_diff(current.splitlines(), page.splitlines(),
                                         "publications.html (committed)",
                                         "publications.html (generated)", lineterm="", n=0))
        added = sum(1 for ln in diff if ln.startswith("+") and not ln.startswith("+++"))
        removed = sum(1 for ln in diff if ln.startswith("-") and not ln.startswith("---"))
        print(f"{PAGE.name} is stale: {added} line(s) would be added, {removed} removed")
        for ln in diff[:40]:
            print("  " + ln[:200])
        if len(diff) > 40:
            print(f"  ... {len(diff) - 40} more diff line(s)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
