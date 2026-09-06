# Topic 3/4 Slidev presentation

This directory contains the eight-minute English presentation for the Lab 4
project. Topic 3 (multicast and bypass) is the main study; Topic 4 trace replay
is presented as a closing case study.

## Run locally

```sh
cd presentation
npm install
npm run dev
```

Open the URL printed by Slidev. Press `Space` or the arrow keys to advance and
press `O` for the slide overview. Presenter mode is available from Slidev's
navigation menu; speaker notes contain the suggested script and timing.

## Build

```sh
npm run build
```

The static site is written to `presentation/dist/`.

PDF export is optional and requires a Playwright Chromium installation:

```sh
npx playwright install chromium
npm run export
```

The figures in `public/` are copies of the accepted report figures under
`report/figures/`. Headline values come from the compact snapshots under
`report/data/`.
