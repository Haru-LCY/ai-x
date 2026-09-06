# Lab 4 presentation

This is an 8-minute Slidev presentation for the Lab 4 project. The main deck
has 13 slides and includes architecture, implementation, evaluation, division
of labor, limitations, and presenter notes.

## Run locally

```bash
cd presentation
npm install
npm run dev
```

Useful Slidev controls:

- `Space` / arrow keys: next slide
- `O`: overview
- `P`: presenter mode with notes
- `F`: fullscreen

## Build and export

```bash
npm run build
npm run export
npm run export:pptx
```

`npm run build` creates the static site under `presentation/dist/`.
`npm run export` creates `presentation/lab4-ai-collectives.pdf` and requires a
Playwright-compatible Chromium installation.
`npm run export:pptx` creates `presentation/lab4-ai-collectives.pptx`. Slidev
exports each page as a high-fidelity slide image, so the PPTX is presentation
ready while the Markdown remains the editable source.

The source of truth is `slides.md`; styling is in `style.css`. Figures are
copied from the reproducible report assets into `public/figures/` so the deck
can be built as a standalone Slidev project.
