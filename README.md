# Chalk Talks — teaching app

`index.html` is now a **single-file app** containing all lessons (currently 64),
re-rendered from one shared template. Everything works offline on an iPad.

## What's inside

- **Home** — search everything (cases, MCQs, pearls, dotphrases — not just
  titles), filter by specialty, track taught/planned per lesson.
- **Lesson pages** — one consistent format: objectives, pre-work, timed teaching
  script (tap a segment's ⏱ chip to start that countdown), interactive cases,
  tap-to-answer MCQs, Anki preview, copyable dotphrase, take-homes. Buttons up
  top open the original slides/PDFs.
- **▶ Teach mode** — full-screen step-through: one segment, case, or MCQ per
  slide, big type, swipe/arrow to advance, built-in segment timer (tap `a⏱` to
  auto-start it on each slide), and a pacing line under the slide counter
  ("8 min in · plan 10 min" — turns red if you're >2 min behind plan).
- **Question bank** (top bar) — every MCQ (currently 320) in one self-graded
  practice view, filterable by specialty, with shuffle and a running score.
  Wrong answers are remembered on-device; the **Missed (n)** chip re-drills
  only those until you answer them correctly.
- **▶ Present slides** — full-screen in-browser slide viewer (swipe/arrow,
  wake-lock) rendering each lesson's `*_slides.pdf` (auto-generated from the
  pptx; regenerate any missing ones with LibreOffice:
  `soffice --headless --convert-to pdf <deck>.pptx`, then rename to
  `<deck>_slides.pdf`). Needs internet once to fetch the pdf.js renderer;
  otherwise it falls back to opening the PDF in the device viewer.
- **PowerPoint online** — on the hosted (https) site only: opens the original
  pptx in Microsoft's free Office viewer (decks ≤10 MB), closest to true
  PowerPoint rendering. Animations don't play in either web mode — for full
  animations open the pptx in the PowerPoint/Keynote app via "Slides (pptx)".
- **Anki ⬇** (top bar) — downloads all cards (currently 1115) as one tagged,
  importable file. Pre-built files also live in `exports/` (combined + per-specialty).
- **◐** — dark mode toggle.

## Folder layout

```
Wrapper/
├── index.html        ← the app (open this / Add to Home Screen)
├── build_app.py      ← regenerates the app from the lesson folders
├── lessons_full.json ← parsed lesson data (auto-written)
├── exports/          ← Anki decks (combined + per-specialty)
├── build_hub.py      ← LEGACY v1 hub builder (superseded; safe to delete)
├── lessons.json      ← LEGACY v1 manifest (safe to delete)
└── <Lesson Name>/    ← one folder per lesson — originals, never modified
    └── *_Lesson_Package.html + slides/PDFs/Anki txt
```

## Adding a lesson

1. Drop the lesson folder (containing a `*_Lesson_Package.html`) into `Wrapper/`.
2. Run `python build_app.py` from the `Wrapper` folder.
3. Done — it's parsed, tagged, searchable, in the question bank, and in the
   Anki exports. The build prints a per-lesson summary and flags anything it
   couldn't parse (`!!NO-MCQ`, etc.).

Tagging is keyword-based; to override, edit `TAG_RULES` at the top of
`build_app.py`.

## iPad (offline, recommended)

Keep `Wrapper` in iCloud Drive → Files app → open `index.html` → Share →
**Add to Home Screen**. Progress and dark-mode choice are saved on the device.
Original slides/PDFs open in the iPad viewers via each lesson's buttons.

## Hosting (optional, synced)

The folder is a complete static site: upload its contents to GitHub Pages
(repo → Settings → Pages → main/root), Netlify Drop, or any static host, then
bookmark the URL on the iPad.

---
Lessons adapted from TeachIM.org (CC BY-NC 4.0 — attribution preserved on each
lesson page). Educational use only; clinician-review content before teaching.
