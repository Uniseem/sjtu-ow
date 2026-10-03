"""Every big picture in the official Overwatch news, with the words around it.

python crawl_v2.py OUT_JSON
1. Lists every article through /news/next-articles?page=N.
2. For each (patch notes, esports and developer Q&A left out) collects the
   CMS pictures (page_media, blog_header, gallery, ...) with alt text and the
   text just before each picture, to tell later which hero or map it shows.
"""

import html
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://overwatch.blizzard.com"
UA = {"User-Agent": "Mozilla/5.0 sjtu-ow-cover-pool", "Accept-Language": "zh-TW,zh;q=0.9"}
DROP = re.compile(r"修正|更新說明|patch|電競|職業|聯賽|OWCS|錦標賽|總監|有問必答|招募|調查|開發者|BlizzCon .*門票|安全|帳號|條款|隱私", re.I)
PICTURE = re.compile(
    r"https://bnetcmsus-a\.akamaihd\.net/cms/(?:page_media|blog_header|gallery|template_resource|content_entry)/"
    r"[^\"'\s)<>]+?\.(?:png|jpe?g|webp)",
    re.I,
)


def get(url):
    """With retries: the CDN now and then answers with the wrong certificate."""
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(request, timeout=40) as response:
                return response.read().decode("utf-8", "replace")
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2 + 2 * attempt)


def list_articles():
    found, seen = [], set()
    first = get(f"{BASE}/zh-tw/news/")
    for href, article_id in re.findall(r'href="((?:/zh-tw)?/news/(\d{8})/[^"]*)"', first):
        if article_id not in seen:
            seen.add(article_id)
            title = re.search(rf'/news/{article_id}/[^"]*"[^>]*>.*?headingtext="([^"]*)"', first, re.S)
            found.append({"id": article_id, "url": BASE + "/zh-tw" + href.replace("/zh-tw", ""), "title": html.unescape(title.group(1)) if title else ""})
    page = 0
    while True:
        text = get(f"{BASE}/news/next-articles?page={page}")
        items = re.findall(r'<a href="(/news/(\d{8})/[^"]*)"[^>]*>.*?headingtext="([^"]*)"', text, re.S)
        new = 0
        for href, article_id, title in items:
            if article_id not in seen:
                seen.add(article_id)
                found.append({"id": article_id, "url": BASE + "/zh-tw" + href, "title": html.unescape(title)})
                new += 1
        if new == 0:
            break
        page += 1
        time.sleep(0.25)
    return found


def pictures(article):
    try:
        text = get(article["url"])
    except Exception as error:
        return article | {"images": [], "error": str(error)}
    images, seen = [], set()
    for match in PICTURE.finditer(text):
        src = match.group(0)
        if src in seen:
            continue
        seen.add(src)
        tag_start = text.rfind("<", 0, match.start())
        tag = text[tag_start : text.find(">", match.end()) + 1]
        alt = html.unescape((re.search(r'alt="([^"]*)"', tag) or [None, ""])[1])
        before = re.sub(r"<[^>]+>", " ", text[max(0, match.start() - 900) : tag_start])
        near = " ".join(html.unescape(before).split())[-160:]
        images.append({"src": src, "alt": alt, "near": near})
    return article | {"images": images}


def main():
    articles = list_articles()
    print("articles listed:", len(articles))
    kept = [a for a in articles if not DROP.search(a["title"])]
    print("after dropping patch notes, esports, Q&A:", len(kept))
    with ThreadPoolExecutor(4) as pool:
        done = list(pool.map(pictures, kept))
    with open(sys.argv[1], "w", encoding="utf-8") as handle:
        json.dump(done, handle, ensure_ascii=False, indent=1)
    unique = {i["src"] for a in done for i in a["images"]}
    print("pictures:", sum(len(a["images"]) for a in done), "unique:", len(unique),
          "errors:", sum(1 for a in done if a.get("error")))


main()
