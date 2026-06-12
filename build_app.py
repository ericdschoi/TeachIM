#!/usr/bin/env python3
"""
build_app.py - Chalk Talks v2: single-file teaching app generator.

Parses every lesson folder's *_Lesson_Package.html into structured data and
renders ONE self-contained app (index.html) with:
  home/search/specialty filters - lesson pages from a shared template -
  teach mode (step-through, timers) - cross-lesson question bank -
  global content search - Anki exports - dark mode - progress tracking.

Original lesson files are never modified. Re-run after adding a lesson:
    python build_app.py
Standard library only. Also writes lessons_full.json and exports/Anki_*.txt.
"""

import html as htmllib
import json
import os
import re
from datetime import datetime
from urllib.parse import quote

HERE = os.environ.get("CT_HERE") or os.path.dirname(os.path.abspath(__file__))
APP_TITLE = "Chalk Talks"

TAG_RULES = [
    (r"pocus|arthrocentesis|paracentesis|thoracentesis|lumbar puncture|central venous|catheter insertion|\binjection\b|ultrasound-guided", "Procedures"),
    (r"uterine|\baub\b|menstr|menopaus|contracept|vaginitis|cervical|abortion|\bovary\b|ovarian|\bpcos\b|gynec|pregnan|obstetric", "Women's Health"),
    (r"depression|anxiety|\bmood\b|psychiat|bipolar|\bptsd\b", "Psychiatry"),
    (r"stroke|\bcva\b|dizziness|vertigo|seizure|\bneuro|delirium|encephal|migraine|headache", "Neurology"),
    (r"electrolyte|hyperkal|hypokal|hyponatrem|hypernatrem|acid.?base|\bsodium|\bpotassium|calcium|magnesium", "Electrolytes"),
    (r"\brenal|kidney|\baki\b|nephr|glomerul|dialysis", "Renal"),
    (r"\bliver\b|hepat|\balf\b|cirrho|biliary|paracent", "Hepatology"),
    (r"diabet|t2dm|\bdm2\b|thyroid|endocr|adrenal|pituitary|osteopor", "Endocrine"),
    (r"\bshock|pressor|ventilat", "Critical Care"),
    (r"heart|cardi|coronary|arrhythm|\bchf\b|myocard|\baf\b|fibrillat|\brvr\b|\bsvt\b|tachycard|syncope|hypertens|\bacs\b|stress.?test|\bcad\b|pericard", "Cardiology"),
    (r"lung|pulm|respir|copd|asthma|pneumon|ards|hypox|pleural|oxygen", "Pulmonary"),
    (r"sepsis|infect|antibiotic|endocard|menin|c\.? ?diff", "Infectious Disease"),
    (r"anemia|leukem|lymphoma|myelo|coag|platelet|hematol|thromb|\bvte\b|dyscrasia|plasma cell|myeloma|paraprotein|amyloid", "Hematology"),
    (r"oncolog|checkpoint|malignan|tumor|chemother|\bcancer", "Oncology"),
    (r"gi |gastro|bowel|pancrea|ulcer|ibd|colitis|cholecyst", "Gastroenterology"),
    (r"arthrit|lupus|vasculit|rheum|gout", "Rheumatology"),
    (r"prevention|screening|vaccin|primary care|transplant|gender", "Primary Care"),
]


def infer_tag(text):
    t = text.lower()
    for pattern, tag in TAG_RULES:
        if re.search(pattern, t):
            return tag
    return "General"


def first(pattern, text, flags=re.I | re.S, group=1, default=""):
    m = re.search(pattern, text, flags)
    return m.group(group).strip() if m else default


def clean(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    return re.sub(r"\s+", " ", htmllib.unescape(s)).strip()


def slugify(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def fix_hrefs(frag, folder):
    """Make relative links in a fragment work from the app at folder-root level."""
    if not frag:
        return frag
    base = quote(folder, safe="()&'-_.~ ")

    def rep(m):
        return m.group(1) + '="' + base + "/" + m.group(2) + '"'
    return re.sub(r'(href|src)="(?!https?:|#|mailto:|data:)([^"]+)"', rep, frag)


def categorize_files(files):
    out = {"presenter": None, "learner_board": None, "handout": None,
           "onepager_pdf": None, "anki": None, "package": None, "other": [],
           "slides": {}}
    for f in files:
        low = f.lower()
        if low.endswith("_lesson_package.html"):
            out["package"] = f
        elif low.endswith("_slides.pdf"):
            out["slides"][f[:-len("_slides.pdf")]] = f
        elif low.endswith(".pptx") and ("optimi" in low or "presenter" in low):
            out["presenter"] = f
        elif low.endswith(".pptx"):
            out["learner_board"] = f
        elif low.endswith(".pdf") and "onepager" in low:
            out["onepager_pdf"] = f
        elif low.endswith(".pdf") and ("handout" in low or "worksheet" in low or "guide" in low):
            out["handout"] = f
        elif low.endswith(".txt") and "anki" in low:
            out["anki"] = f
        elif low.endswith((".pdf", ".pptx", ".docx", ".txt", ".html")):
            out["other"].append(f)
    return out


ALIAS = {
    "files": "files", "objectives": "objectives", "obj": "objectives",
    "prework": "prework", "script": "script", "cases": "cases", "case": "cases",
    "mcq": "mcq", "mcqs": "mcq", "anki": "anki", "cards": "anki",
    "dotphrase": "dotphrase", "dot": "dotphrase", "takehome": "takehome",
    "changelog": "changelog", "refs": "refs", "ref": "refs",
}


def parse_lesson(folder_name):
    folder = os.path.join(HERE, folder_name)
    files = sorted(os.listdir(folder))
    pkg = next((f for f in files if f.lower().endswith("_lesson_package.html")), None)
    if not pkg:
        return None
    with open(os.path.join(folder, pkg), encoding="utf-8") as fh:
        doc = fh.read()

    raw_title = htmllib.unescape(first(r"<title>(.*?)</title>", doc)) or folder_name
    title = re.split(r"\s+[—\-]\s+(?:Optimized\s+)?Lesson Package", raw_title)[0]
    title = re.split(r"\s+[—\-]\s+Optimized", title)[0].strip()
    header = first(r"<header>(.*?)</header>", doc) or ""
    ps = re.findall(r"<p[^>]*>(.*?)</p>", header, re.S)
    subtitle = clean(ps[0]) if ps else ""
    credit = ""
    msmall = re.search(r'<p class="small">(.*?)</p>', header, re.S)
    if msmall:
        credit = fix_hrefs(msmall.group(1).strip(), folder_name)

    duration = ""
    for p in ps:
        m = re.search(r"(\d+\s*[–\-]?\s*\d*\s*min[^.;·]*)", clean(p), re.I)
        if m:
            duration = m.group(1).strip()
            break

    raw_sections = {}
    order = []
    for m in re.finditer(r'<section id="([^"]+)"[^>]*>(.*?)</section>', doc, re.S):
        raw_sections[m.group(1)] = m.group(2)
        order.append(m.group(1))
    # normalize variant section ids to canonical names (first occurrence wins)
    sections = {}
    for sid in order:
        canon = ALIAS.get(sid)
        if canon and canon not in sections:
            sections[canon] = raw_sections[sid]

    def body_of(sid):
        b = sections.get(sid, "")
        return re.sub(r"<h2>.*?</h2>", "", b, count=1, flags=re.S).strip()

    def label_of(sid):
        return clean(re.sub(r"<span[^>]*>.*?</span>", "",
                            first(r"<h2>(.*?)</h2>", sections.get(sid, "")), flags=re.S))

    # objectives
    ol = first(r"(<ol[^>]*>.*?</ol>)", sections.get("objectives", ""))
    objectives = [clean(li) for li in re.findall(r"<li>(.*?)</li>", ol, re.S)]

    # prework
    prework = []
    for d in re.findall(r"<details>(.*?)</details>", sections.get("prework", ""), re.S):
        q = clean(first(r"<summary>(.*?)</summary>", d))
        a = fix_hrefs(re.sub(r"<summary>.*?</summary>", "", d, flags=re.S).strip(), folder_name)
        if q:
            prework.append({"q": q, "a": a})

    # script segments - supports <h3>...<span class="time"> and <div class="seg">...(N min)
    segments = []
    script = body_of("script")
    markers = list(re.finditer(r'<h3>(.*?)</h3>|<div class="seg">(.*?)</div>', script, re.S))
    for idx, mk in enumerate(markers):
        head = mk.group(1) if mk.group(1) is not None else mk.group(2)
        start = mk.end()
        end = markers[idx + 1].start() if idx + 1 < len(markers) else len(script)
        content = fix_hrefs(script[start:end].strip(), folder_name)
        mins = first(r'class="time">\s*(\d+)', head, default="") or first(r"\((\d+)\s*min", head, default="")
        label = clean(re.sub(r"<span[^>]*>.*?</span>", "", head, flags=re.S))
        if label:
            segments.append({"label": label, "min": int(mins) if mins else None, "html": content})

    # cases
    cases = []
    cases_label = label_of("cases") or "Cases"
    cases_intro = ""
    cb = body_of("cases")
    if "<h3>" in cb:
        intro = cb.split("<h3>")[0]
        cases_intro = fix_hrefs(re.sub(r'<p class="small">.*?</p>', "", intro, flags=re.S).strip(), folder_name)
        for ch in re.split(r"(?=<h3>)", cb):
            if not ch.strip().startswith("<h3>"):
                continue
            ctitle = clean(first(r"<h3>(.*?)</h3>", ch))
            after = re.sub(r"<h3>.*?</h3>", "", ch, count=1, flags=re.S)
            stem = fix_hrefs(after.split("<details>")[0].strip(), folder_name)
            reveal = fix_hrefs(re.sub(r"<summary>.*?</summary>", "",
                                      first(r"<details>(.*?)</details>", after), flags=re.S).strip(), folder_name)
            cases.append({"title": ctitle, "stem": stem, "reveal": reveal})
    else:
        cases_intro = fix_hrefs(cb.split("<details>")[0].strip(), folder_name)
        for i, d in enumerate(re.findall(r"<details>(.*?)</details>", cb, re.S), 1):
            stem = first(r"<summary>(.*?)</summary>", d)
            reveal = re.sub(r"<summary>.*?</summary>", "", d, flags=re.S).strip()
            cases.append({"title": cases_label + " " + str(i),
                          "stem": "<p>" + stem + "</p>", "reveal": fix_hrefs(reveal, folder_name)})

    # MCQs - split on the opening tag so a nested <div class="stem"> can't truncate a block.
    # stem is <div class="stem"> (newer) or the leading <p> (older); options <ol ...>.
    mcqs = []
    for blk in re.split(r'<div class="mcq">', sections.get("mcq", ""))[1:]:
        stem = clean(first(r'<div class="stem">(.*?)</div>', blk) or first(r"<p>(.*?)</p>", blk))
        stem = re.sub(r"^\d+\.\s*", "", stem)
        opts = [clean(li) for li in re.findall(r"<li>(.*?)</li>", first(r"(<ol[^>]*>.*?</ol>)", blk), re.S)]
        if not opts:
            # inline-options format: <p>A. ... · B. ... · C. ...</p>
            optp = next((clean(p) for p in re.findall(r"<p>(.*?)</p>", blk, re.S)
                         if re.match(r"\s*A[\.\)]\s", clean(p))), "")
            if optp:
                opts = [re.sub(r"^[A-E][\.\)]\s*", "", x).strip()
                        for x in re.split(r"\s*[·•|]\s*|\s+(?=[A-E][\.\)]\s)", optp)
                        if re.match(r"[A-E][\.\)]", x.strip())]
        det = first(r"<details>(.*?)</details>", blk)
        ans = first(r"<b>\s*([A-E])\b", det, default="")
        exp = fix_hrefs(re.sub(r"<summary>.*?</summary>", "", det, flags=re.S).strip(), folder_name)
        if stem and opts:
            mcqs.append({"stem": stem, "opts": opts, "ans": ans, "exp": exp})

    # take-home
    takehome = [clean(li) for li in re.findall(
        r"<li>(.*?)</li>", first(r"(<ol[^>]*>.*?</ol>)", sections.get("takehome", "")), re.S)]

    # dotphrase - prefer the <pre> inside the dotphrase section, fall back to id="dp"
    dot = htmllib.unescape(first(r"<pre[^>]*>(.*?)</pre>", sections.get("dotphrase", ""))
                           or first(r'<pre id="dp">(.*?)</pre>', doc))

    # extras = any section with no canonical alias (update, antibiogram, ...)
    extras = []
    for sid in order:
        if sid not in ALIAS:
            extras.append({"id": sid,
                           "label": clean(first(r"<h2>(.*?)</h2>", raw_sections[sid])) or sid.title(),
                           "html": fix_hrefs(
                               re.sub(r"<h2>.*?</h2>", "", raw_sections[sid], count=1, flags=re.S).strip(),
                               folder_name)})

    refs = fix_hrefs(body_of("refs"), folder_name)
    changelog = fix_hrefs(body_of("changelog"), folder_name)

    fmeta = categorize_files(files)
    if fmeta["presenter"]:
        try:
            fmeta["presenter_mb"] = round(
                os.path.getsize(os.path.join(folder, fmeta["presenter"])) / 1048576, 1)
        except OSError:
            fmeta["presenter_mb"] = None
    # anki cards from TSV
    anki = []
    if fmeta["anki"]:
        with open(os.path.join(folder, fmeta["anki"]), encoding="utf-8") as fh:
            for line in fh:
                if "\t" in line:
                    f_, b_ = line.rstrip("\n").split("\t", 1)
                    if f_.strip():
                        anki.append([f_.strip(), b_.strip()])

    tag = infer_tag(folder_name + " " + title)
    return {
        "slug": slugify(title), "folder": folder_name, "package": pkg,
        "title": title, "tag": tag, "duration": duration, "subtitle": subtitle,
        "credit": credit, "objectives": objectives, "prework": prework,
        "segments": segments, "casesLabel": cases_label, "casesIntro": cases_intro,
        "cases": cases, "mcqs": mcqs, "anki": anki, "dot": dot,
        "takehome": takehome, "extras": extras, "refs": refs,
        "changelog": changelog, "files": fmeta,
    }


def discover():
    out = []
    for name in sorted(os.listdir(HERE)):
        p = os.path.join(HERE, name)
        if os.path.isdir(p) and not name.startswith((".", "_")):
            meta = parse_lesson(name)
            if meta:
                out.append(meta)
    return out


# ============================ APP TEMPLATE =================================
TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Chalk Talks">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="icon" type="image/png" href="favicon.png">
<meta name="theme-color" content="#f2f5f7">
<title>Chalk Talks - IM teaching library</title>
<style>
:root{
  --bg:#f2f5f7;--card:#ffffff;--ink:#101c26;--mut:#5b6b78;--line:#dbe3e9;
  --acc:#0c7187;--accSoft:#e3f0f4;--warm:#b4530a;--warmSoft:#fbf1e7;
  --good:#247a4d;--goodSoft:#e9f5ee;--shadow:0 1px 2px rgba(15,30,40,.06),0 8px 24px rgba(15,30,40,.07);
  --r:14px;--fs:17px;
}
[data-theme="dark"]{
  --bg:#0d141a;--card:#16212b;--ink:#e7eef3;--mut:#8da0af;--line:#26343f;
  --acc:#4db7cf;--accSoft:#143341;--warm:#e8a063;--warmSoft:#33281c;
  --good:#5cc28e;--goodSoft:#16301f;--shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.35);
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html{font-size:var(--fs);-webkit-text-size-adjust:100%}
button,summary,.btn,.chip,.card,.res,.opt,.state,.timechip,.tclock{touch-action:manipulation}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
  line-height:1.55;padding:env(safe-area-inset-top) 0 env(safe-area-inset-bottom)}
a{color:var(--acc)}
.topbar{position:sticky;top:0;z-index:30;background:var(--card);border-bottom:1px solid var(--line);
  display:flex;align-items:center;gap:8px;padding:10px 14px;box-shadow:var(--shadow)}
.topbar .brand{font-weight:700;font-size:1.05rem;letter-spacing:.01em;cursor:pointer;display:flex;align-items:center;gap:9px}
.brand .dot{width:26px;height:26px;border-radius:7px;background:var(--acc);color:#fff;display:flex;
  align-items:center;justify-content:center;font-size:.72rem;font-weight:700}
.topbar .spacer{flex:1}
.iconbtn{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:10px;
  padding:8px 12px;font-size:.86rem;cursor:pointer;white-space:nowrap}
.iconbtn.acc{background:var(--acc);color:#fff;border-color:var(--acc)}
.wrap{max-width:1020px;margin:0 auto;padding:18px 16px 80px}
h1{font-size:1.7rem;margin:.3em 0 .15em;line-height:1.2}
h2.sec{font-size:1.12rem;margin:1.8em 0 .6em;color:var(--acc);text-transform:uppercase;
  letter-spacing:.06em;font-size:.85rem;font-weight:700}
.sub{color:var(--mut);font-size:.92rem}
.pill{display:inline-block;font-size:.74rem;font-weight:600;border-radius:999px;padding:3px 11px}
.search{width:100%;font-size:1rem;padding:13px 16px;border:1px solid var(--line);border-radius:13px;
  background:var(--card);color:var(--ink);outline:none;box-shadow:var(--shadow)}
.search:focus{border-color:var(--acc)}
.chips{display:flex;gap:8px;overflow-x:auto;padding:12px 0 4px;-webkit-overflow-scrolling:touch;scrollbar-width:none}
.chips::-webkit-scrollbar{display:none}
.chip{flex:0 0 auto;font-size:.84rem;padding:8px 15px;border-radius:999px;border:1px solid var(--line);
  background:var(--card);color:var(--ink);cursor:pointer}
.chip.on{background:var(--acc);color:#fff;border-color:var(--acc)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;margin-top:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);
  padding:16px 16px 13px;display:flex;flex-direction:column;cursor:pointer}
.card .row1{display:flex;justify-content:space-between;align-items:center;gap:8px}
.card h3{margin:9px 0 3px;font-size:1.08rem;line-height:1.3}
.card .meta{color:var(--mut);font-size:.82rem;display:flex;gap:10px;flex-wrap:wrap}
.card .foot{display:flex;gap:8px;margin-top:12px;align-items:center}
.btn{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:10px;
  padding:9px 14px;font-size:.86rem;cursor:pointer;text-decoration:none;text-align:center}
.btn.acc{background:var(--acc);color:#fff;border-color:var(--acc);font-weight:600}
.btn.warm{color:var(--warm);border-color:var(--warm)}
.state{width:30px;height:30px;border-radius:999px;border:1.5px solid var(--line);background:var(--card);
  color:var(--mut);cursor:pointer;font-size:.9rem;flex:0 0 auto}
.state.taught{color:var(--good);border-color:var(--good);background:var(--goodSoft)}
.state.planned{color:var(--warm);border-color:var(--warm);background:var(--warmSoft)}
.results{margin-top:10px;display:flex;flex-direction:column;gap:8px}
.res{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:11px 14px;cursor:pointer}
.res .where{font-size:.74rem;color:var(--warm);font-weight:700;text-transform:uppercase;letter-spacing:.05em}
.res .snip{font-size:.9rem;color:var(--mut)}
.res b{color:var(--ink)}
/* lesson view */
.lhead{padding:6px 0 0}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 4px}
.secnav{position:sticky;top:57px;z-index:25;background:var(--bg);padding:8px 0;margin:0 -2px}
.content section{background:var(--card);border:1px solid var(--line);border-radius:var(--r);
  padding:18px 20px;margin:14px 0;box-shadow:var(--shadow);scroll-margin-top:130px}
.content h3{font-size:1.02rem;margin:1.4em 0 .4em;color:var(--warm)}
.content h3:first-child{margin-top:0}
.content table{border-collapse:collapse;width:100%;font-size:.88rem;margin:10px 0;display:block;overflow-x:auto}
.content th,.content td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
.content th{background:var(--accSoft);color:var(--ink)}
.timechip{display:inline-block;font-size:.72rem;font-weight:700;color:#fff;background:var(--warm);
  border-radius:999px;padding:2px 10px;margin-left:8px;vertical-align:middle;cursor:pointer}
.ask{background:var(--warmSoft);border-left:4px solid var(--warm);padding:10px 14px;margin:12px 0;border-radius:0 10px 10px 0}
.ask b{color:var(--warm);font-size:.8rem;letter-spacing:.05em}
.pearl{background:var(--goodSoft);border-left:4px solid var(--good);padding:10px 14px;margin:12px 0;border-radius:0 10px 10px 0}
.seg{font-weight:700;color:var(--acc);margin:16px 0 4px;font-size:1.02rem}
details.qa{border:1px solid var(--line);border-radius:11px;padding:11px 15px;margin:10px 0;background:var(--card)}
details.qa summary{cursor:pointer;font-weight:600;font-size:.94rem;color:var(--acc)}
details.qa[open]{background:var(--accSoft)}
.case{border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:12px 0}
.case .ct{font-weight:700;margin-bottom:6px}
.reveal-btn{margin-top:8px;border:1px solid var(--acc);color:var(--acc);background:transparent;
  border-radius:10px;padding:9px 16px;font-size:.88rem;cursor:pointer}
.reveal-body{margin-top:10px;border-top:1px dashed var(--line);padding-top:10px;display:none}
.mcqcard{border:1px solid var(--line);border-radius:12px;padding:15px 16px;margin:12px 0}
.mcqcard .stem{font-weight:600;margin-bottom:9px}
.opt{display:block;width:100%;text-align:left;border:1px solid var(--line);background:var(--card);color:var(--ink);
  border-radius:10px;padding:10px 13px;margin:6px 0;font-size:.92rem;cursor:pointer}
.opt.correct{border-color:var(--good);background:var(--goodSoft)}
.opt.wrong{border-color:#c0392b;background:rgba(192,57,43,.12)}
.exp{margin-top:10px;font-size:.92rem;border-top:1px dashed var(--line);padding-top:10px;display:none}
.mcqsrc{font-size:.76rem;color:var(--mut);margin-top:8px}
pre.dot{background:var(--accSoft);border:1px solid var(--line);border-radius:11px;padding:14px;
  font-size:.8rem;overflow-x:auto;white-space:pre-wrap;line-height:1.45;font-family:ui-monospace,Menlo,Consolas,monospace}
code{background:var(--accSoft);padding:1px 6px;border-radius:6px;font-size:.88em}
.credit{font-size:.78rem;color:var(--mut);margin:20px 0;line-height:1.5}
/* teach mode */
.teach{position:fixed;inset:0;z-index:50;background:var(--bg);display:flex;flex-direction:column}
.teach .slide{flex:1;overflow-y:auto;padding:26px 22px 18px;max-width:880px;margin:0 auto;width:100%;font-size:1.16rem}
.teach .slide h2{font-size:1.55rem;margin:0 0 12px}
.teach .nav{display:flex;align-items:center;gap:10px;padding:12px 16px calc(12px + env(safe-area-inset-bottom));
  background:var(--card);border-top:1px solid var(--line)}
.teach .nav .ctr{flex:1;text-align:center;color:var(--mut);font-size:.9rem}
.tclock{font-variant-numeric:tabular-nums;font-weight:700;font-size:1.15rem;min-width:74px;text-align:center;
  border:1px solid var(--line);border-radius:10px;padding:7px 10px;cursor:pointer}
.tclock.run{color:var(--warm);border-color:var(--warm)}
.tclock.over{color:#c0392b;border-color:#c0392b}
.sess{font-size:.72rem;color:var(--mut);font-weight:400;line-height:1.3}
.sess.behind{color:#c0392b;font-weight:700}
.pslide{flex:1;display:flex;align-items:center;justify-content:center;overflow:hidden;background:#000}
.pslide canvas{box-shadow:var(--shadow)}
.pslide .empty{color:#bbb}
.pslide .empty a{color:#7fd0e4}
.bigreveal{font-size:1.05rem;padding:13px 22px}
.fab{position:fixed;right:16px;bottom:calc(16px + env(safe-area-inset-bottom));z-index:40;background:var(--warm);
  color:#fff;border:none;border-radius:999px;width:56px;height:56px;font-size:22px;box-shadow:var(--shadow);cursor:pointer}
.score{font-size:.95rem;color:var(--mut);margin:8px 0}
.empty{text-align:center;color:var(--mut);padding:48px 0}
@media(max-width:560px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="topbar">
  <div class="brand" onclick="go('#/')"><span class="dot">CT</span><span>Chalk Talks</span></div>
  <div class="spacer"></div>
  <button class="iconbtn" onclick="go('#/bank')">Question bank</button>
  <button class="iconbtn" onclick="exportAnki()">Anki &#8595;</button>
  <button class="iconbtn" id="themeBtn" onclick="toggleTheme()" aria-label="Toggle dark mode">&#9680;</button>
</div>
<div class="wrap" id="app"></div>
<button class="fab" id="fab" onclick="fabTimer()" title="Timer" aria-label="Timer">&#9201;</button>

<script id="data" type="application/json">__DATA__</script>
<script>
"use strict";
const DATA = JSON.parse(document.getElementById("data").textContent);
const BY = {}; DATA.forEach(l=>BY[l.slug]=l);
const TAGS = [...new Set(DATA.map(l=>l.tag))].sort();
const TAGCOL = {"Cardiology":["#fdecec","#a32d2d"],"Critical Care":["#f3e9fb","#6b2fa0"],
 "Electrolytes":["#e8f1fc","#185fa5"],"Endocrine":["#fdf3e4","#8a5a09"],"Hematology":["#fbeaf0","#993556"],
 "Hepatology":["#f0f5e3","#3b6d11"],"Infectious Disease":["#e9f7f1","#0f6e56"],"Oncology":["#efedfb","#473ba6"],
 "Pulmonary":["#e6f4f8","#0b6376"],"Renal":["#e3f0f4","#0c7187"],"Procedures":["#eaeef2","#3a4a5c"],
 "Women's Health":["#fceef5","#8a2d5c"],"Psychiatry":["#efeafb","#5b3a9e"],"Neurology":["#eaedfb","#33409e"],
 "Gastroenterology":["#fbf0e6","#8a4b14"],"Rheumatology":["#fdeee8","#9a4422"],
 "Primary Care":["#e8f3ee","#1f6b4a"],"General":["#eef0f2","#444"]};
const PKEY="chalktalks_progress_v1";
const store={get(k){try{return localStorage.getItem(k)}catch(e){return null}},
 set(k,v){try{localStorage.setItem(k,v)}catch(e){}}};
let prog={}; try{prog=JSON.parse(store.get(PKEY)||"{}")}catch(e){}
const saveProg=()=>store.set(PKEY,JSON.stringify(prog));
let theme=store.get("ct_theme")||(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");
applyTheme();
function applyTheme(){document.documentElement.setAttribute("data-theme",theme);
  const m=document.querySelector('meta[name="theme-color"]');
  if(m)m.content=theme==="dark"?"#0d141a":"#f2f5f7";}
function toggleTheme(){theme=theme==="dark"?"light":"dark";store.set("ct_theme",theme);applyTheme();}
function esc(s){return (s||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
function enc(p){return encodeURI(p);}
function go(h){location.hash=h;}
function pill(tag){const c=TAGCOL[tag]||TAGCOL.General;
 return '<span class="pill" style="background:'+c[0]+';color:'+c[1]+'">'+esc(tag)+'</span>';}

let homeState={q:"",tag:"All",untaught:false};

function render(){
  const h=location.hash||"#/";
  stopTeachTimer();
  const overlay=h.startsWith("#/teach/")||h.startsWith("#/present/");
  if(!h.startsWith("#/teach/")){teach=null;stopSess();}
  if(!h.startsWith("#/present/"))pres=null;
  if(!overlay){relWake();
    const tr=document.getElementById("teachRoot");if(tr)tr.innerHTML="";}
  document.getElementById("fab").style.display = overlay ? "none" : "";
  if(h.startsWith("#/lesson/")) return renderLesson(h.split("/")[2]);
  if(h.startsWith("#/teach/")) return renderTeach(h.split("/")[2]);
  if(h.startsWith("#/present/")) return renderPresent(h.split("/")[2]);
  if(h==="#/bank") return renderBank();
  renderHome();
}
window.addEventListener("hashchange",render);

/* ---------------- HOME ---------------- */
function renderHome(){
  const app=document.getElementById("app");
  let html='<h1 style="margin-top:4px">Chalk Talks</h1>'+
    '<div class="sub">'+DATA.length+' interactive chalk talks - tap a lesson, or play to teach</div>'+
    '<div style="margin-top:14px"><input class="search" id="q" type="search" autocomplete="off" autocorrect="off" autocapitalize="none" spellcheck="false" enterkeyhint="search" placeholder="Search everything - lessons, cases, questions, pearls..." value="'+esc(homeState.q)+'"></div>'+
    '<div class="chips" id="chips"></div><div id="list"></div>';
  app.innerHTML=html;
  const q=document.getElementById("q");
  q.addEventListener("input",()=>{homeState.q=q.value;drawList();});
  drawChips(); drawList();
}
function drawChips(){
  const box=document.getElementById("chips"); if(!box)return;
  let h='<button class="chip'+(homeState.tag==="All"&&!homeState.untaught?" on":"")+'" onclick="homeState.tag=\'All\';homeState.untaught=false;drawChips();drawList()">All</button>';
  TAGS.forEach((t,i)=>{h+='<button class="chip'+(homeState.tag===t?" on":"")+'" onclick="pickTag('+i+')">'+esc(t)+'</button>';});
  h+='<button class="chip'+(homeState.untaught?" on":"")+'" onclick="homeState.untaught=!homeState.untaught;drawChips();drawList()">Not taught</button>';
  box.innerHTML=h;
}
function pickTag(i){const t=TAGS[i];homeState.tag=(homeState.tag===t?"All":t);drawChips();drawList();}
function drawList(){
  const box=document.getElementById("list"); if(!box)return;
  const q=homeState.q.trim().toLowerCase();
  if(q.length>1){box.innerHTML=searchResults(q);return;}
  let h='<div class="grid">',n=0;
  DATA.forEach(l=>{
    if(homeState.tag!=="All"&&l.tag!==homeState.tag)return;
    const p=prog[l.folder]||{};
    if(homeState.untaught&&p.status==="taught")return;
    n++;
    const st=p.status==="taught"?"taught":(p.status==="planned"?"planned":"");
    const mark=p.status==="taught"?"✓":(p.status==="planned"?"◷":"○");
    h+='<div class="card" onclick="go(\'#/lesson/'+l.slug+'\')">'+
      '<div class="row1">'+pill(l.tag)+'<button class="state '+st+'" onclick="event.stopPropagation();cycle(\''+l.slug+'\')">'+mark+'</button></div>'+
      '<h3>'+esc(l.title)+'</h3>'+
      '<div class="meta">'+(l.duration?'<span>⏱ '+esc(l.duration)+'</span>':'')+
      '<span>'+l.cases.length+' cases - '+l.mcqs.length+' MCQs - '+l.anki.length+' cards</span></div>'+
      '<div class="foot"><button class="btn acc" style="flex:1" onclick="event.stopPropagation();go(\'#/teach/'+l.slug+'\')">▶ Teach</button>'+
      '<a class="btn" href="'+enc(l.folder+"/"+l.package)+'" onclick="event.stopPropagation()">Original</a></div>'+
      (p.status==="taught"?'<div class="sub" style="margin-top:8px;color:var(--good)">Taught '+(p.date||"")+(p.note?" - "+esc(p.note):"")+'</div>':"")+
      '</div>';
  });
  h+='</div>';
  box.innerHTML=n?h:'<div class="empty">Nothing matches.</div>';
}
function cycle(slug){
  const l=BY[slug];const p=prog[l.folder]||{};
  const next=p.status==="taught"?null:(p.status==="planned"?"taught":"planned");
  if(!next){delete prog[l.folder];}
  else{const rec={status:next};
    if(next==="taught"){rec.date=new Date().toISOString().slice(0,10);
      const note=window.prompt("Session note (optional):",p.note||"");if(note)rec.note=note;}
    prog[l.folder]=rec;}
  saveProg();
  if((location.hash||"#/")==="#/"){drawList();}else{render();}
}

/* ---------------- SEARCH ---------------- */
let INDEX=null;
function buildIndex(){
  INDEX=[];
  DATA.forEach(l=>{
    const add=(where,label,text,anchor)=>{const t=(text||"").trim();
      if(t)INDEX.push({slug:l.slug,title:l.title,where:where,label:label,text:t,lower:t.toLowerCase(),anchor:anchor});};
    add("Lesson",l.title,l.title+" "+l.tag,"");
    l.objectives.forEach(o=>add("Objective","",o,"s-objectives"));
    l.takehome.forEach(t=>add("Take-home","",t,"s-takehome"));
    l.cases.forEach((c,i)=>add("Case",c.title,strip(c.stem)+" "+strip(c.reveal),"case-"+i));
    l.mcqs.forEach((m,i)=>add("MCQ","",m.stem,"mcq-"+l.slug+"-"+i));
    l.prework.forEach(p=>add("Pre-work","",p.q,"s-prework"));
    l.segments.forEach(s=>add("Script",s.label,strip(s.html).slice(0,400),"s-script"));
    if(l.dot)add("Dotphrase","",l.dot,"s-dot");
  });
}
function strip(h){const d=document.createElement("div");d.innerHTML=h||"";return d.textContent||"";}
function searchResults(q){
  if(!INDEX)buildIndex();
  const hits=INDEX.filter(e=>e.lower.includes(q)).slice(0,50);
  if(!hits.length)return '<div class="empty">No matches for "'+esc(q)+'".</div>';
  let h='<div class="results">';
  hits.forEach(e=>{
    const i=e.lower.indexOf(q);
    const snip=esc(e.text.slice(Math.max(0,i-50),i))+"<b>"+esc(e.text.substr(i,q.length))+"</b>"+esc(e.text.substr(i+q.length,70));
    h+='<div class="res" onclick="go(\'#/lesson/'+e.slug+(e.anchor?"@"+e.anchor:"")+'\')">'+
       '<div class="where">'+e.where+' - '+esc(e.title)+'</div>'+
       (e.label&&e.where!=="Lesson"?'<div style="font-weight:600;font-size:.9rem">'+esc(e.label)+'</div>':"")+
       '<div class="snip">...'+snip+'...</div></div>';
  });
  return h+"</div>";
}

/* ---------------- LESSON ---------------- */
function renderLesson(slugAnchor){
  const [slug,anchor]=slugAnchor.split("@");
  const l=BY[slug]; if(!l){go("#/");return;}
  const f=l.files;const app=document.getElementById("app");
  const fl=(file,label)=>file?'<a class="btn" href="'+enc(l.folder+"/"+file)+'">'+label+'</a>':"";
  let secs=[["s-objectives","Objectives"],["s-prework","Pre-work"],["s-script","Script"]];
  if(l.cases.length)secs.push(["s-cases",l.casesLabel||"Cases"]);
  if(l.mcqs.length)secs.push(["s-mcq","MCQs"]);
  if(l.anki.length)secs.push(["s-anki","Cards"]);
  if(l.dot)secs.push(["s-dot","Dotphrase"]);
  if(l.takehome.length)secs.push(["s-takehome","Take-home"]);
  const spdf=slidesPdfOf(l);
  let h='<div class="lhead">'+pill(l.tag)+'<h1>'+esc(l.title)+'</h1>'+
    '<div class="sub">'+esc(l.subtitle)+'</div>'+
    '<div class="actions"><button class="btn acc" onclick="go(\'#/teach/'+l.slug+'\')">▶ Teach mode</button>'+
    (spdf?'<button class="btn warm" onclick="go(\'#/present/'+l.slug+'\')">▶ Present slides</button>':"")+
    (onlineViewOk(l)?'<a class="btn" target="_blank" rel="noopener" href="'+officeUrl(l)+'">PowerPoint online</a>':"")+
    fl(f.presenter,"Slides (pptx)")+fl(f.onepager_pdf,"One-pager")+fl(f.handout,"Handout")+fl(f.anki,"Anki.txt")+
    '<a class="btn" href="'+enc(l.folder+"/"+l.package)+'">Original</a></div></div>'+
    '<div class="secnav"><div class="chips">'+
    secs.map(s=>'<button class="chip" onclick="jump(\''+s[0]+'\')">'+esc(s[1])+'</button>').join("")+
    '</div></div><div class="content">';

  h+='<section id="s-objectives"><h2 class="sec">Learning objectives</h2><ol>'+
     l.objectives.map(o=>"<li>"+esc(o)+"</li>").join("")+"</ol></section>";

  if(l.prework.length){h+='<section id="s-prework"><h2 class="sec">Pre-work - send the day before</h2>'+
    l.prework.map(p=>'<details class="qa"><summary>'+esc(p.q)+"</summary>"+p.a+"</details>").join("")+"</section>";}

  h+='<section id="s-script"><h2 class="sec">Teaching script'+(l.duration?" - "+esc(l.duration):"")+"</h2>";
  l.segments.forEach(s=>{h+='<div class="seg">'+esc(s.label)+(s.min?'<span class="timechip" onclick="setTimer('+s.min+',\''+esc(s.label).replace(/'/g,"\\'")+'\')">'+s.min+" min ⏱</span>":"")+"</div>"+s.html;});
  h+="</section>";

  l.extras.forEach(x=>{h+='<section><h2 class="sec">'+esc(x.label)+"</h2>"+x.html+"</section>";});

  if(l.cases.length){h+='<section id="s-cases"><h2 class="sec">'+esc(l.casesLabel)+"</h2>"+(l.casesIntro||"");
    l.cases.forEach((c,i)=>{h+='<div class="case" id="case-'+i+'"><div class="ct">'+esc(c.title)+"</div>"+c.stem+
      '<button class="reveal-btn" onclick="rev(this)">Reveal answer</button><div class="reveal-body">'+c.reveal+"</div></div>";});
    h+="</section>";}

  if(l.mcqs.length){h+='<section id="s-mcq"><h2 class="sec">Board-style MCQs</h2>'+
    l.mcqs.map((m,i)=>mcqHTML(m,l.slug+"-"+i,null,l.slug+"-"+i)).join("")+"</section>";}

  if(l.anki.length){h+='<section id="s-anki"><h2 class="sec">Spaced-repetition cards ('+l.anki.length+")</h2>"+
    l.anki.slice(0,6).map(c=>'<details class="qa"><summary>'+esc(c[0])+"</summary><p>"+esc(c[1])+"</p></details>").join("")+
    (f.anki?'<p class="sub"><a href="'+enc(l.folder+"/"+f.anki)+'">Full deck ('+l.anki.length+' cards, Anki-importable)</a></p>':"")+"</section>";}

  if(l.dot){h+='<section id="s-dot"><h2 class="sec">Attending dotphrase</h2>'+
    '<button class="btn" onclick="copyDot(\''+l.slug+'\',this)">Copy to clipboard</button>'+
    '<pre class="dot">'+esc(l.dot)+"</pre></section>";}

  if(l.takehome.length){h+='<section id="s-takehome"><h2 class="sec">Take-home points</h2><ol>'+
    l.takehome.map(t=>"<li>"+esc(t)+"</li>").join("")+"</ol></section>";}

  if(l.refs)h+='<section><details class="qa"><summary>References</summary>'+l.refs+"</details>"+
    (l.changelog?'<details class="qa"><summary>Optimization changelog</summary>'+l.changelog+"</details>":"")+"</section>";
  h+="</div>"+(l.credit?'<div class="credit">'+l.credit+"</div>":"");
  app.innerHTML=h;
  window.scrollTo(0,0);
  if(anchor)setTimeout(()=>jump(anchor),60);
}
function jump(id){const el=document.getElementById(id);if(el)el.scrollIntoView({behavior:"smooth",block:"start"});}
function rev(btn){const b=btn.nextElementSibling;const open=b.style.display==="block";
  b.style.display=open?"none":"block";btn.textContent=open?"Reveal answer":"Hide answer";}
function copyDot(slug,btn){
  const txt=BY[slug].dot;
  const done=()=>{btn.textContent="Copied ✓";setTimeout(()=>btn.textContent="Copy to clipboard",1500);};
  if(navigator.clipboard&&window.isSecureContext)
    navigator.clipboard.writeText(txt).then(done,()=>fallbackCopy(txt,done));
  else fallbackCopy(txt,done);
}
function fallbackCopy(t,done){
  const ta=document.createElement("textarea");ta.value=t;
  ta.style.cssText="position:fixed;top:0;left:0;opacity:0";ta.setAttribute("readonly","");
  document.body.appendChild(ta);ta.select();ta.setSelectionRange(0,t.length);
  try{if(document.execCommand("copy"))done();}catch(e){}
  ta.remove();
}
const MKEY="ct_missed_v1";
let missed={}; try{missed=JSON.parse(store.get(MKEY)||"{}")}catch(e){}
function mcqHTML(m,uid,src,qid){
  let h='<div class="mcqcard" id="mcq-'+uid+'"><div class="stem">'+esc(m.stem)+"</div>";
  m.opts.forEach((o,j)=>{const letter="ABCDE"[j];
    h+='<button class="opt" onclick="pick(this,\''+uid+'\',\''+letter+'\',\''+(m.ans||"")+'\',\''+(qid||"")+'\')"><b>'+letter+".</b> "+esc(o)+"</button>";});
  h+='<div class="exp">'+(m.exp||"")+"</div>"+(src?'<div class="mcqsrc">'+esc(src)+"</div>":"")+"</div>";
  return h;
}
let bankScore={right:0,total:0};
function pick(btn,uid,chosen,ans,qid){
  const card=document.getElementById("mcq-"+uid);
  if(card.dataset.done)return;card.dataset.done=1;
  card.querySelectorAll(".opt").forEach(o=>{
    const letter=o.querySelector("b").textContent[0];
    if(letter===ans)o.classList.add("correct");
    else if(o===btn)o.classList.add("wrong");
    o.style.pointerEvents="none";});
  card.querySelector(".exp").style.display="block";
  if(qid){ /* personal retrieval log - not recorded in teach mode (group answers) */
    if(chosen===ans)delete missed[qid];else missed[qid]=1;
    store.set(MKEY,JSON.stringify(missed));}
  if(location.hash==="#/bank"){bankScore.total++;if(chosen===ans)bankScore.right++;
    const s=document.getElementById("score");if(s)s.textContent="Score: "+bankScore.right+" / "+bankScore.total;}
}

/* ---------------- QUESTION BANK ---------------- */
let bankState={tag:"All",order:null,missedOnly:false};
function renderBank(){
  const app=document.getElementById("app");
  const all=[];DATA.forEach(l=>l.mcqs.forEach((m,i)=>all.push({m:m,l:l,i:i,qid:l.slug+"-"+i})));
  const nMissed=all.filter(x=>missed[x.qid]).length;
  let pool=bankState.tag==="All"?all:all.filter(x=>x.l.tag===bankState.tag);
  if(bankState.missedOnly)pool=pool.filter(x=>missed[x.qid]);
  if(bankState.order)pool=bankState.order.map(i=>pool[i]).filter(Boolean);
  let h='<h1 style="margin-top:4px">Question bank</h1><div class="sub">'+all.length+
    " board-style MCQs across "+DATA.length+" lessons - self-graded</div>"+
    '<div class="chips"><button class="chip'+(bankState.tag==="All"?" on":"")+'" onclick="bankTag(-1)">All</button>'+
    TAGS.map((t,i)=>'<button class="chip'+(bankState.tag===t?" on":"")+'" onclick="bankTag('+i+')">'+esc(t)+"</button>").join("")+
    '<button class="chip'+(bankState.missedOnly?" on":"")+'" onclick="bankMissed()">Missed ('+nMissed+')</button></div>'+
    '<div style="display:flex;gap:8px;align-items:center;margin:6px 0 2px">'+
    '<button class="btn" onclick="shuffleBank('+pool.length+')">Shuffle</button>'+
    '<button class="btn" onclick="bankScore={right:0,total:0};renderBank()">Reset</button>'+
    '<span class="score" id="score">Score: '+bankScore.right+" / "+bankScore.total+"</span></div>";
  pool.forEach((x,k)=>{h+=mcqHTML(x.m,"bank-"+k,x.l.title+" - "+x.l.tag,x.qid);});
  app.innerHTML=h+(pool.length?"":'<div class="empty">'+
    (bankState.missedOnly?"No missed questions here - nice.":"No questions in this filter.")+"</div>");
  window.scrollTo(0,0);
}
function bankTag(i){bankState.tag=i<0?"All":TAGS[i];bankState.order=null;renderBank();}
function bankMissed(){bankState.missedOnly=!bankState.missedOnly;bankState.order=null;renderBank();}
function shuffleBank(n){const o=[...Array(n).keys()];
  for(let i=n-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[o[i],o[j]]=[o[j],o[i]];}
  bankState.order=o;renderBank();}

/* ---------------- TEACH MODE ---------------- */
let teach=null,tInt=null,tRem=0,tRun=false,tEnd=0,wakeL=null,sessInt=null;
let autoT=store.get("ct_autotimer")==="1";
function toggleAuto(){autoT=!autoT;store.set("ct_autotimer",autoT?"1":"");
  if(teach)drawTeach();}
function startSess(){if(sessInt)clearInterval(sessInt);
  sessInt=setInterval(updSess,1000);}
function stopSess(){if(sessInt){clearInterval(sessInt);sessInt=null;}}
function updSess(){
  const e=document.getElementById("sess");if(!e||!teach)return;
  const m=Math.floor((Date.now()-teach.start)/60000);
  const plan=teach.slides[teach.i].at;
  e.textContent=m+" min in · plan "+plan+" min";
  e.classList.toggle("behind",m>plan+2);}
function reqWake(){if("wakeLock" in navigator)navigator.wakeLock.request("screen").then(w=>{wakeL=w;},()=>{});}
function relWake(){if(wakeL){wakeL.release().catch(()=>{});wakeL=null;}}
document.addEventListener("visibilitychange",()=>{if((teach||pres)&&document.visibilityState==="visible")reqWake();});
function renderTeach(slug){
  const l=BY[slug];if(!l){go("#/");return;}
  tRem=0;reqWake();
  const slides=[{type:"title"}];
  l.segments.forEach(s=>slides.push({type:"seg",s:s}));
  l.cases.forEach((c,i)=>slides.push({type:"case",c:c,i:i}));
  l.mcqs.forEach((m,i)=>slides.push({type:"mcq",m:m,i:i}));
  if(l.takehome.length)slides.push({type:"take"});
  /* cumulative planned minutes: "by this slide you should be at X min" */
  let cum=0;
  slides.forEach(sl=>{sl.at=cum;if(sl.type==="seg"&&sl.s.min)cum+=sl.s.min;});
  teach={l:l,slides:slides,i:0,start:Date.now()};
  startSess();
  document.getElementById("app").innerHTML="";
  let d=document.getElementById("teachRoot");
  if(!d){d=document.createElement("div");d.id="teachRoot";document.body.appendChild(d);}
  drawTeach();
}
function drawTeach(){
  const t=teach;if(!t)return;
  const l=t.l,sl=t.slides[t.i];
  let body="";
  if(sl.type==="title"){body='<h2>'+esc(l.title)+"</h2><div class='sub'>"+esc(l.subtitle)+"</div><h3 style='margin-top:22px'>Objectives</h3><ol>"+
    l.objectives.map(o=>"<li>"+esc(o)+"</li>").join("")+"</ol>";}
  else if(sl.type==="seg"){body="<h2>"+esc(sl.s.label)+"</h2>"+sl.s.html;}
  else if(sl.type==="case"){body="<h2>"+esc(sl.c.title)+"</h2>"+sl.c.stem+
    '<button class="reveal-btn bigreveal" onclick="rev(this)">Reveal answer</button><div class="reveal-body">'+sl.c.reveal+"</div>";}
  else if(sl.type==="mcq"){body="<h2>Question "+(sl.i+1)+" / "+l.mcqs.length+"</h2>"+
    mcqHTML(sl.m,"teach-"+l.slug+"-"+sl.i,null,null);}
  else{body="<h2>Take-home points</h2><ol>"+l.takehome.map(x=>"<li>"+esc(x)+"</li>").join("")+"</ol>";}
  const segMin=sl.type==="seg"?sl.s.min:null;
  document.getElementById("teachRoot").innerHTML=
    '<div class="teach"><div class="slide content" id="slideBox">'+body+"</div>"+
    '<div class="nav"><button class="iconbtn" onclick="exitTeach()" aria-label="Exit teach mode">✕</button>'+
    '<button class="iconbtn" onclick="step(-1)" aria-label="Previous slide">‹</button>'+
    '<div class="ctr">'+(t.i+1)+" / "+t.slides.length+'<div class="sess" id="sess"></div></div>'+
    '<button class="iconbtn'+(autoT?" acc":"")+'" onclick="toggleAuto()" title="Auto-start segment timer" aria-label="Auto-start segment timer">a⏱</button>'+
    '<div class="tclock" id="tclock" onclick="tapClock('+(segMin||0)+')" role="button" aria-label="Segment timer">'+(segMin?segMin+":00":"--:--")+"</div>"+
    '<button class="iconbtn acc" onclick="step(1)" aria-label="Next slide">›</button></div></div>';
  stopTeachTimer();
  if(segMin){tRem=segMin*60;if(autoT)tapClock(segMin);}
  updSess();
  const box=document.getElementById("slideBox");
  let x0=null,y0=null;
  box.addEventListener("touchstart",e=>{x0=e.touches[0].clientX;y0=e.touches[0].clientY;},{passive:true});
  box.addEventListener("touchend",e=>{if(x0===null)return;
    const dx=e.changedTouches[0].clientX-x0,dy=e.changedTouches[0].clientY-y0;
    if(Math.abs(dx)>70&&Math.abs(dx)>1.5*Math.abs(dy))step(dx<0?1:-1);
    x0=y0=null;},{passive:true});
}
function step(d){if(!teach)return;const n=teach.i+d;
  if(n<0||n>=teach.slides.length)return;teach.i=n;drawTeach();}
let actx=null;
function unlockAudio(){try{actx=actx||new (window.AudioContext||window.webkitAudioContext)();
  if(actx.resume)actx.resume();}catch(e){}}
function beep(){try{if(!actx)return;
  const o=actx.createOscillator(),g=actx.createGain();o.frequency.value=880;
  g.gain.setValueAtTime(.3,actx.currentTime);g.gain.exponentialRampToValueAtTime(.001,actx.currentTime+.7);
  o.connect(g);g.connect(actx.destination);o.start();o.stop(actx.currentTime+.7);}catch(e){}}
function tapClock(min){
  if(tRun){tRem=Math.round((tEnd-Date.now())/1000);stopTeachTimer();return;}
  if(tRem<=0)tRem=(min||5)*60;
  tEnd=Date.now()+tRem*1000;
  unlockAudio();
  tRun=true;document.getElementById("tclock").classList.add("run");
  tInt=setInterval(()=>{const c=document.getElementById("tclock");if(!c){stopTeachTimer();return;}
    const prev=tRem;tRem=Math.round((tEnd-Date.now())/1000);
    const m=Math.floor(Math.abs(tRem)/60),s=Math.abs(tRem)%60;
    c.textContent=(tRem<0?"-":"")+m+":"+String(s).padStart(2,"0");
    if(tRem<0)c.classList.add("over");
    if(prev>0&&tRem<=0){beep();if(navigator.vibrate)navigator.vibrate(500);}},500);
}
function stopTeachTimer(){if(tInt){clearInterval(tInt);tInt=null;}tRun=false;
  const c=document.getElementById("tclock");if(c)c.classList.remove("run");}
function exitTeach(){go("#/lesson/"+location.hash.split("/")[2]);}
document.addEventListener("keydown",e=>{if(!teach)return;
  if(e.key==="ArrowRight")step(1);if(e.key==="ArrowLeft")step(-1);
  if(e.key===" "&&e.target.tagName!=="BUTTON"){e.preventDefault();step(1);}
  if(e.key==="Escape")exitTeach();});

/* ---------------- TIMER FAB (lesson/home) ---------------- */
let fabInt=null,fabEnd=0;
function fabTimer(){
  if(fabInt){clearInterval(fabInt);fabInt=null;
    const fab=document.getElementById("fab");fab.textContent="⏱";fab.style.fontSize="22px";return;}
  const mins=window.prompt("Minutes (e.g. 5):","5");if(!mins)return;
  setTimer(parseFloat(mins),mins+" min");
}
function setTimer(min,label){
  if(fabInt){clearInterval(fabInt);fabInt=null;}
  if(!(min>0))return;
  unlockAudio();
  fabEnd=Date.now()+Math.round(min*60)*1000;
  const fab=document.getElementById("fab");
  fab.style.fontSize="15px";
  let prev=1;
  fabInt=setInterval(()=>{const r=Math.round((fabEnd-Date.now())/1000);
    const m=Math.floor(Math.abs(r)/60),s=Math.abs(r)%60;
    fab.textContent=(r<0?"-":"")+m+":"+String(s).padStart(2,"0");
    if(prev>0&&r<=0){beep();if(navigator.vibrate)navigator.vibrate(500);}
    prev=r;
    if(r<-5400){clearInterval(fabInt);fabInt=null;fab.textContent="⏱";fab.style.fontSize="22px";}},500);
  if(label)fab.title=label;
}

/* ---------------- PRESENT MODE (PDF slides) ---------------- */
let pres=null,pdfjsLoading=null;
function slidesPdfOf(l){const f=l.files;if(!f.slides)return null;
  const pb=f.presenter?f.presenter.replace(/\.pptx$/i,""):null;
  return (pb&&f.slides[pb])||Object.values(f.slides)[0]||null;}
function onlineViewOk(l){return location.protocol==="https:"&&
  !/^(localhost|127\.)/.test(location.hostname)&&l.files.presenter&&
  (l.files.presenter_mb==null||l.files.presenter_mb<=10);}
function officeUrl(l){
  const abs=new URL(enc(l.folder+"/"+l.files.presenter),location.href).href;
  return "https://view.officeapps.live.com/op/embed.aspx?src="+encodeURIComponent(abs);}
function loadPdfjs(cb){
  if(window.pdfjsLib){cb(true);return;}
  if(pdfjsLoading){pdfjsLoading.push(cb);return;}
  pdfjsLoading=[cb];
  const s=document.createElement("script");
  s.src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js";
  s.onload=()=>{const q=pdfjsLoading;pdfjsLoading=null;q.forEach(f=>f(true));};
  s.onerror=()=>{const q=pdfjsLoading;pdfjsLoading=null;q.forEach(f=>f(false));};
  document.head.appendChild(s);
}
function renderPresent(slug){
  const l=BY[slug];if(!l){go("#/");return;}
  const spdf=slidesPdfOf(l);if(!spdf){go("#/lesson/"+slug);return;}
  const url=enc(l.folder+"/"+spdf);
  reqWake();
  document.getElementById("app").innerHTML="";
  let d=document.getElementById("teachRoot");
  if(!d){d=document.createElement("div");d.id="teachRoot";document.body.appendChild(d);}
  d.innerHTML='<div class="teach"><div class="pslide" id="pslide"><div class="empty">Loading slides…</div></div>'+
    '<div class="nav"><button class="iconbtn" onclick="exitPres(\''+slug+'\')" aria-label="Close">✕</button>'+
    '<button class="iconbtn" onclick="pstep(-1)" aria-label="Previous slide">‹</button>'+
    '<div class="ctr" id="pctr">– / –</div>'+
    '<a class="iconbtn" href="'+url+'" target="_blank" rel="noopener" title="Open the PDF directly">PDF</a>'+
    '<button class="iconbtn acc" onclick="pstep(1)" aria-label="Next slide">›</button></div></div>';
  const fallback=msg=>{const ps=document.getElementById("pslide");
    if(ps)ps.innerHTML='<div class="empty">'+msg+' — <a href="'+url+'" target="_blank" rel="noopener">open the PDF directly</a>.</div>';};
  loadPdfjs(ok=>{
    if(!ok||!window.pdfjsLib){fallback("In-app viewer needs internet the first time");return;}
    pdfjsLib.GlobalWorkerOptions.workerSrc="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
    pdfjsLib.getDocument(url).promise.then(
      pdf=>{if(location.hash!=="#/present/"+slug)return;
        pres={pdf:pdf,n:pdf.numPages,i:1,slug:slug};drawPres();},
      ()=>fallback("Couldn't load the slides here"));
  });
  const ps=document.getElementById("pslide");
  let x0=null,y0=null;
  ps.addEventListener("touchstart",e=>{x0=e.touches[0].clientX;y0=e.touches[0].clientY;},{passive:true});
  ps.addEventListener("touchend",e=>{if(x0===null)return;
    const dx=e.changedTouches[0].clientX-x0,dy=e.changedTouches[0].clientY-y0;
    if(Math.abs(dx)>70&&Math.abs(dx)>1.5*Math.abs(dy))pstep(dx<0?1:-1);
    x0=y0=null;},{passive:true});
}
function drawPres(){
  if(!pres)return;
  const ctr=document.getElementById("pctr");if(ctr)ctr.textContent=pres.i+" / "+pres.n;
  pres.pdf.getPage(pres.i).then(page=>{
    const box=document.getElementById("pslide");if(!box||!pres)return;
    const dpr=window.devicePixelRatio||1;
    const v1=page.getViewport({scale:1});
    const scale=Math.min(box.clientWidth/v1.width,box.clientHeight/v1.height)*dpr;
    const vp=page.getViewport({scale:scale});
    const c=document.createElement("canvas");c.width=vp.width;c.height=vp.height;
    c.style.width=(vp.width/dpr)+"px";c.style.height=(vp.height/dpr)+"px";
    page.render({canvasContext:c.getContext("2d"),viewport:vp}).promise.then(()=>{
      if(!pres)return;box.innerHTML="";box.appendChild(c);});
  });
}
function pstep(d){if(!pres)return;const n=pres.i+d;if(n<1||n>pres.n)return;pres.i=n;drawPres();}
function exitPres(slug){go("#/lesson/"+slug);}
document.addEventListener("keydown",e=>{if(!pres)return;
  if(e.key==="ArrowRight")pstep(1);if(e.key==="ArrowLeft")pstep(-1);
  if(e.key===" "&&e.target.tagName!=="BUTTON"&&e.target.tagName!=="A"){e.preventDefault();pstep(1);}
  if(e.key==="Escape")exitPres(pres.slug);});
window.addEventListener("resize",()=>{if(pres)drawPres();});

/* ---------------- ANKI EXPORT ---------------- */
function exportAnki(){
  let rows=[];
  DATA.forEach(l=>l.anki.forEach(c=>rows.push(c[0]+"\t"+c[1]+"\t"+l.tag.replace(/\s+/g,"_")+"::"+l.slug)));
  const blob=new Blob([rows.join("\n")],{type:"text/plain"});
  const a=document.createElement("a");a.href=URL.createObjectURL(blob);
  a.download="ChalkTalks_Anki_All.txt";a.click();URL.revokeObjectURL(a.href);
}
render();
</script>
</body>
</html>
"""


def build():
    lessons = discover()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(os.path.join(HERE, "lessons_full.json"), "w", encoding="utf-8") as fh:
        json.dump({"generated": stamp, "lessons": lessons}, fh, indent=1, ensure_ascii=False)

    data = json.dumps(lessons, ensure_ascii=False).replace("</", "<\\/")
    page = TEMPLATE.replace("__DATA__", data)
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(page)

    # Anki exports
    exp = os.path.join(HERE, "exports")
    os.makedirs(exp, exist_ok=True)
    by_tag = {}
    allrows = []
    for l in lessons:
        for f_, b_ in l["anki"]:
            row = f_ + "\t" + b_ + "\t" + l["tag"].replace(" ", "_") + "::" + l["slug"]
            allrows.append(row)
            by_tag.setdefault(l["tag"], []).append(row)
    with open(os.path.join(exp, "Anki_All.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(allrows))
    for tag, rows in by_tag.items():
        with open(os.path.join(exp, "Anki_" + tag.replace(" ", "_") + ".txt"), "w",
                  encoding="utf-8") as fh:
            fh.write("\n".join(rows))

    ncases = sum(len(l["cases"]) for l in lessons)
    nmcq = sum(len(l["mcqs"]) for l in lessons)
    ncards = sum(len(l["anki"]) for l in lessons)
    nslides = sum(1 for l in lessons if l["files"].get("slides"))
    print("Built app: %d lessons | %d cases | %d MCQs | %d Anki cards | %d with slide PDFs"
          % (len(lessons), ncases, nmcq, ncards, nslides))
    for l in lessons:
        flags = []
        if not l["objectives"]: flags.append("NO-OBJ")
        if not l["segments"]: flags.append("NO-SCRIPT")
        if not l["mcqs"]: flags.append("NO-MCQ")
        if not l["anki"]: flags.append("NO-ANKI")
        if not l["cases"]: flags.append("NO-CASES")
        if not l["files"].get("slides"): flags.append("NO-SLIDEPDF")
        mcq_noans = sum(1 for m in l["mcqs"] if not m["ans"])
        if mcq_noans: flags.append("%d-MCQ-NO-ANS" % mcq_noans)
        print("  - %s [%s] obj=%d seg=%d cases=%d mcq=%d anki=%d %s"
              % (l["title"], l["tag"], len(l["objectives"]), len(l["segments"]),
                 len(l["cases"]), len(l["mcqs"]), len(l["anki"]),
                 " ".join("!!" + f for f in flags)))
    print("Wrote: index.html, lessons_full.json, exports/")


if __name__ == "__main__":
    build()
