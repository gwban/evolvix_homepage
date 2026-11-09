#!/usr/bin/env python3
"""Build the Evolvix static site from ``src/`` into ``_site/``.

Standard library only (Python 3.9+). The shared layout (header, footer, meta tags)
lives in one file, ``src/layout.html``; each page in ``src/pages/<lang>/`` holds only
its own content. The build also writes ``sitemap.xml`` / ``robots.txt`` and verifies
that every local link and image in the output exists.

Usage:
    python3 build.py                 # build into _site/
    python3 -m http.server 8000 -d _site   # preview at http://localhost:8000
"""
from __future__ import annotations

import re
import shutil
import sys
from dataclasses import dataclass
from datetime import date
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from string import Template
from urllib.parse import quote, unquote, urlparse

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
OUT = ROOT / "_site"
SITE_URL = "https://evolvix.co.kr/"
EMAIL = "evolvix@evolvix.co.kr"

LANGS = ("ko", "en")                      # first entry is the default language (served at /)
PAGE_IDS = ("index", "inspection", "monitoring", "product", "about", "careers", "contact")
NAV_IDS = ("inspection", "monitoring", "product", "about", "careers", "contact")
PAGE_SCRIPTS = {"index": ("story.js",), "inspection": ("story.js",)}   # page id → scripts in src/assets/js (deferred)

STRINGS = {
    "ko": {
        "site_name": "이볼빅스 Evolvix",
        "skip": "본문 바로가기",
        "home_label": "이볼빅스 홈",
        "nav_label": "주요 메뉴",
        "footer_nav_label": "사이트 메뉴",
        "lang_label": "언어 선택",
        "og_locale": "ko_KR",
        "company": "주식회사 이볼빅스",
        "ceo": "대표 반근우",
        "address": "경기도 광명시 일직로 43 GIDC A동 1906호",
        "nav": {"inspection": "머신비전 검사", "monitoring": "공정 모니터링", "product": "RMS-ON",
                "about": "회사소개", "careers": "채용", "contact": "문의"},
        # (subject, body) for mailto links; body is a fill-in template
        "mail": {
            "consult": ("[도입 상담] ", ""),
            "sample": ("[샘플 테스트 의뢰] ",
                       "검사 대상(제품/소재):\n찾으려는 결함 또는 측정 항목:\n라인 속도:\n"
                       "샘플 수량 / 발송 예정일:\n회사명 / 담당자 / 연락처:\n"),
            "pilot": ("[파일럿 협업] ", ""),
            "job": ("[입사 지원] ", ""),
        },
    },
    "en": {
        "site_name": "Evolvix",
        "skip": "Skip to content",
        "home_label": "Evolvix home",
        "nav_label": "Main menu",
        "footer_nav_label": "Site menu",
        "lang_label": "Language",
        "og_locale": "en_US",
        "company": "Evolvix Inc.",
        "ceo": "CEO Geunwoo Ban",
        "address": "Room 1906, Building A, GIDC, 43 Iljik-ro, Gwangmyeong-si, Gyeonggi-do, Republic of Korea",
        "nav": {"inspection": "Machine Vision", "monitoring": "Monitoring", "product": "RMS-ON",
                "about": "About", "careers": "Careers", "contact": "Contact"},
        "mail": {
            "consult": ("[Consultation] ", ""),
            "sample": ("[Sample Test Request] ",
                       "What to inspect (product/material):\nDefects or dimensions to check:\nLine speed:\n"
                       "Number of samples / shipping date:\nCompany / name / phone:\n"),
            "pilot": ("[Pilot Collaboration] ", ""),
            "job": ("[Job Application] ", ""),
        },
    },
}

# Reusable markup, referenced from page files as {{waves}}, {{wave_lines}}, {{icon:name}}.
_WAVE = "M0 60C120 20 240 20 360 60S600 100 720 60 960 20 1080 60 1320 100 1440 60V120H0Z"
SNIPPETS = {
    "waves": (
        '<div class="waves" aria-hidden="true">'
        + "".join(
            f'<svg class="wave-{i}" viewBox="0 0 1440 120" preserveAspectRatio="none">'
            f'<path d="{_WAVE}"/></svg>'
            for i in (1, 2, 3, 4)
        )
        + "</div>"
    ),
    "wave_lines": (
        '<div class="wave-lines" aria-hidden="true">'
        '<svg viewBox="0 0 1440 200" preserveAspectRatio="none">'
        '<path d="M0 100C180 40 360 40 540 100S900 160 1080 100 1260 40 1440 100"/>'
        '<path d="M0 130C180 80 360 80 540 130S900 180 1080 130 1260 80 1440 130"/>'
        '<path d="M0 160C180 120 360 120 540 160S900 200 1080 160 1260 120 1440 160"/>'
        "</svg></div>"
    ),
}

# Twinkling points over the dark hero: (left %, top %, size px, delay s, duration s)
_SPARKLES = ((12, 64, 6, 0.6, 3.2), (21, 72, 4, 1.9, 2.6), (30, 58, 5, 1.1, 3.6), (38, 70, 7, 2.6, 3.0),
             (47, 62, 4, 0.9, 2.8), (55, 74, 6, 2.1, 3.4), (63, 60, 5, 1.4, 2.7), (71, 68, 7, 0.3, 3.8),
             (79, 57, 4, 2.9, 2.9), (86, 66, 6, 1.6, 3.3), (92, 60, 4, 0.7, 2.5), (8, 78, 5, 2.3, 3.1))
SNIPPETS["sparkles"] = (
    '<div class="sparkles" aria-hidden="true">'
    + "".join(f'<i style="left:{x}%;top:{y}%;--s:{sz}px;--delay:{d}s;--dur:{t}s"></i>'
              for x, y, sz, d, t in _SPARKLES)
    + "</div>"
)

_SVG = ('<span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{}</svg></span>')
ICONS = {
    "sensing": '<circle cx="12" cy="12" r="2"/><path d="M8 8a5.5 5.5 0 0 0 0 8M16 8a5.5 5.5 0 0 1 0 8M5 5a10 10 0 0 0 0 14M19 5a10 10 0 0 1 0 14"/>',
    "network": '<circle cx="12" cy="5" r="2.2"/><circle cx="5" cy="18" r="2.2"/><circle cx="19" cy="18" r="2.2"/><path d="M11 7 6 16M13 7l5 9M7.2 18h9.6"/>',
    "gateway": '<rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 16.5h.01M11 16.5h.01M12 13V9M8.5 6.5a5 5 0 0 1 7 0"/>',
    "predict": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/><path d="m14 7 3-3 3 3"/>',
    "pulse": '<path d="M3 12h4l2-5 4 10 2-5h6"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "wrench": '<path d="M14.5 6.5a4 4 0 0 0-5.3 5.3L4 17l3 3 5.2-5.2a4 4 0 0 0 5.3-5.3l-2.5 2.5-2.5-.5-.5-2.5z"/>',
    "shield": '<path d="M12 3 4 6v6c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V6z"/><path d="m9 12 2 2 4-4"/>',
    "bulb": '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "people": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14.5a6.5 6.5 0 0 1 3.5 5.5"/>',
    "box": '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.4-4.4"/>',
    "ruler": '<path d="M3 17 17 3l4 4L7 21z"/><path d="m7 13 2 2M10 10l2 2M13 7l2 2"/>',
    "layers": '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/>',
    "battery": '<rect x="2.5" y="7" width="16" height="10" rx="2"/><path d="M21.5 11v2M6.5 10v4M10.5 10v4"/>',
    "roll": '<ellipse cx="7" cy="12" rx="3" ry="7"/><path d="M7 5h10M7 19h10M17 5c1.7 0 3 3.1 3 7s-1.3 7-3 7"/>',
    "flask": '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.7 3h10.6a2 2 0 0 0 1.7-3l-5-9V3"/><path d="M7.5 15h9"/>',
    "factory": '<path d="M4 20V10l5 3V10l5 3V6l6 4v10z"/><path d="M8 20v-3M12 20v-3M16 20v-3"/>',
}

META_RE = re.compile(r"\A<!--\s*\n(.*?)\n-->\s*\n", re.S)
TOKEN_RE = re.compile(r"\{\{\s*([a-z_]+)(?::([a-z_]+))?\s*\}\}")


class BuildError(Exception):
    pass


@dataclass(frozen=True)
class Page:
    lang: str
    page_id: str
    title: str
    description: str
    body: str

    @property
    def path(self) -> str:
        """URL path relative to the site root, e.g. '' or 'en/about/'."""
        return url_path(self.lang, self.page_id)


def url_path(lang: str, page_id: str) -> str:
    prefix = "" if lang == LANGS[0] else f"{lang}/"
    return prefix + ("" if page_id == "index" else f"{page_id}/")


def rel_root(path: str) -> str:
    """Relative prefix from a page at ``path`` back to the site root."""
    return "../" * path.count("/") or "./"


def href(from_path: str, to_path: str) -> str:
    return rel_root(from_path) + to_path


def mailto(subject: str, body: str = "") -> str:
    """mailto: URL (HTML-attribute escaped) with a pre-filled subject and optional body."""
    query = "subject=" + quote(subject)
    if body:
        query += "&body=" + quote(body.replace("\n", "\r\n"))   # RFC 6068 line breaks
    return escape(f"mailto:{EMAIL}?{query}")


def load_page(file: Path, lang: str, page_id: str) -> Page:
    text = file.read_text(encoding="utf-8")
    match = META_RE.match(text)
    if not match:
        raise BuildError(f"{file}: missing metadata comment block")
    meta = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    for key in ("title", "description"):
        if not meta.get(key):
            raise BuildError(f"{file}: metadata '{key}' is required")
    return Page(lang, page_id, meta["title"], meta["description"], text[match.end():])


def expand_tokens(body: str, page: Page, root: str) -> str:
    base = root + url_path(page.lang, "index")

    def replace(m: re.Match) -> str:
        name, arg = m.group(1), m.group(2)
        if name == "icon":
            if arg not in ICONS:
                raise BuildError(f"{page.lang}/{page.page_id}: unknown icon '{arg}'")
            return _SVG.format(ICONS[arg])
        values = {"root": root, "base": base, "email": EMAIL, **SNIPPETS,
                  **{f"mail_{k}": mailto(*v) for k, v in STRINGS[page.lang]["mail"].items()}}
        if arg is not None or name not in values:
            raise BuildError(f"{page.lang}/{page.page_id}: unknown token '{m.group(0)}'")
        return values[name]

    return TOKEN_RE.sub(replace, body)


def render(layout: Template, page: Page, *, absolute: bool = False) -> str:
    s = STRINGS[page.lang]
    root = "/" if absolute else rel_root(page.path)
    link = (lambda to: "/" + to) if absolute else (lambda to: href(page.path, to))

    current_page = ' aria-current="page"'
    current_lang = ' aria-current="true"'
    nav = "\n".join(
        '          <li><a href="{}"{}>{}</a></li>'.format(
            link(url_path(page.lang, pid)), current_page if pid == page.page_id else "", s["nav"][pid])
        for pid in NAV_IDS
    )
    switch_target = page.page_id if page.page_id in PAGE_IDS else "index"
    lang_switch = "\n".join(
        '        <a href="{}" lang="{}" hreflang="{}"{}>{}</a>'.format(
            link(url_path(lang, switch_target)), lang, lang,
            current_lang if lang == page.lang else "", lang.upper())
        for lang in LANGS
    )
    if page.page_id in PAGE_IDS:
        head_links = [f'  <link rel="canonical" href="{SITE_URL}{page.path}">']
        head_links += [
            f'  <link rel="alternate" hreflang="{lang}" href="{SITE_URL}{url_path(lang, page.page_id)}">'
            for lang in LANGS
        ]
        head_links.append(f'  <link rel="alternate" hreflang="x-default" href="{SITE_URL}{url_path(LANGS[0], page.page_id)}">')
    else:
        head_links = ['  <meta name="robots" content="noindex">']

    title = page.title if page.page_id == "index" else f"{page.title} | {s['site_name']}"
    return layout.substitute(
        lang=page.lang,
        title=escape(title),
        description=escape(page.description),
        head_links="\n".join(head_links),
        og_locale=s["og_locale"],
        site_url=SITE_URL,
        root=root,
        home=link(url_path(page.lang, "index")),
        nav=nav,
        lang_switch=lang_switch,
        content=expand_tokens(page.body, page, root),
        scripts="\n".join(f'  <script src="{root}assets/js/{name}" defer></script>'
                           for name in PAGE_SCRIPTS.get(page.page_id, ())),
        email=EMAIL,
        year=date.today().year,
        **{k: s[k] for k in ("skip", "home_label", "nav_label", "footer_nav_label",
                             "lang_label", "company", "ceo", "address")},
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sitemap() -> str:
    urls = []
    for lang in LANGS:
        for pid in PAGE_IDS:
            alts = "".join(
                f'\n    <xhtml:link rel="alternate" hreflang="{alt}" href="{SITE_URL}{url_path(alt, pid)}"/>'
                for alt in LANGS
            )
            urls.append(f"  <url>\n    <loc>{SITE_URL}{url_path(lang, pid)}</loc>{alts}\n  </url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' + "\n".join(urls) + "\n</urlset>\n")


class _RefCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []
        self.ids: list[str] = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ("href", "src") and value:
                self.refs.append(value)
            elif key == "id":
                self.ids.append(value)


def verify(out: Path) -> list[str]:
    """Return problems found in the built site (broken local refs, duplicate ids, leftover tokens)."""
    problems = []
    for file in sorted(out.rglob("*.html")):
        text = file.read_text(encoding="utf-8")
        name = file.relative_to(out).as_posix()
        if "{{" in text or "${" in text:
            problems.append(f"{name}: unexpanded template token")
        parser = _RefCollector()
        parser.feed(text)
        dups = sorted({i for i in parser.ids if parser.ids.count(i) > 1})
        if dups:
            problems.append(f"{name}: duplicate ids {dups}")
        for ref in parser.refs:
            url = urlparse(ref)
            if url.scheme or ref.startswith("//"):
                continue
            if ref.startswith("#"):
                if ref[1:] not in parser.ids:
                    problems.append(f"{name}: broken anchor {ref}")
                continue
            target = out / unquote(url.path).lstrip("/") if ref.startswith("/") else file.parent / unquote(url.path)
            if target.is_dir():
                target = target / "index.html"
            if not target.resolve().is_file():
                problems.append(f"{name}: missing {ref}")
    return problems


def build() -> None:
    layout = Template((SRC / "layout.html").read_text(encoding="utf-8"))

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC / "assets", OUT / "assets")

    count = 0
    for lang in LANGS:
        for pid in PAGE_IDS:
            file = SRC / "pages" / lang / f"{pid}.html"
            if not file.is_file():
                raise BuildError(f"missing page: {file.relative_to(ROOT)}")
            page = load_page(file, lang, pid)
            write(OUT / page.path / "index.html", render(layout, page))
            count += 1

    not_found = load_page(SRC / "pages" / "404.html", LANGS[0], "404")
    write(OUT / "404.html", render(layout, not_found, absolute=True))

    write(OUT / "sitemap.xml", sitemap())
    write(OUT / "robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n")

    problems = verify(OUT)
    if problems:
        raise BuildError("verification failed:\n  " + "\n  ".join(problems))
    print(f"Built {count} pages + 404 into {OUT.relative_to(ROOT)}/ — all local links verified.")


if __name__ == "__main__":
    try:
        build()
    except BuildError as exc:
        print(f"Build error: {exc}", file=sys.stderr)
        sys.exit(1)
