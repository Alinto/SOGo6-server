#!/usr/bin/env python3
"""
Parcourt les fichiers HTML dans le répertoire build/docs et génère search.json.
Usage:
  python3 scripts/generate_search_index.py build/docs
"""
import sys
import os
import json
from bs4 import BeautifulSoup

def text_from_soup(soup):
    # retire scripts/styles et renvoie le texte visible
    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    return soup.get_text(separator=" ", strip=True)

def index_html_file(path, rel_url):
    with open(path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "lxml")
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        # essayer de prendre le h1 ou la partie principale
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)
        body_text = text_from_soup(soup.body if soup.body else soup)
        excerpt = body_text[:300] + ("…" if len(body_text) > 300 else "")
        return {
            "url": rel_url,
            "title": title,
            "content": body_text,
            "excerpt": excerpt
        }

def main(out_dir):
    entries = []
    for root, _, files in os.walk(out_dir):
        for fname in files:
            if not fname.endswith(".html"):
                continue
            if fname == "search.html":
                continue
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, out_dir)
            # convertir windows separators en url-friendly
            rel_url = rel.replace(os.path.sep, "/")
            try:
                entry = index_html_file(full, rel_url)
                entries.append(entry)
            except Exception as e:
                print(f"Warning: failed to index {full}: {e}", file=sys.stderr)
    outpath = os.path.join(out_dir, "search.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"Wrote {outpath} ({len(entries)} pages).")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: generate_search_index.py <build_dir>", file=sys.stderr)
        sys.exit(2)
    main(sys.argv[1])