# Topic 3/4 Slidev presentation (presentation2)

Eight-minute presentation for the Lab 4 project, restructured for clarity:
four numbered sections — Architecture, Implementation, Evaluation, and
Division of Labor. Topic 3 (bypass + multicast) is the main study; the
Topic 4 H100 trace replay closes the evaluation section.

## Structure

| Section | Slides | Content |
| --- | --- | --- |
| Title + roadmap | 1–2 | Scope and the paired-comparison rule |
| 01 Architecture | 3–5 | Garnet Mesh XY baseline, multicast design, bypass design |
| 02 Implementation | 6–8 | Multicast mechanisms, bypass oracle + deadlock audit, Topic 4 trace pipeline |
| 03 Evaluation | 9–13 | Methodology, multicast, bypass, interaction, trace results |
| Conclusion + 04 Division of Labor | 14–15 | Three separate claims, who built what |
| Backup | 16–17 | Evaluation contract, interpretation boundaries |

Speaker notes in presenter mode contain the suggested script and timing
(about 8 minutes total).

## Slide source layout

`slides.md` remains the Slidev entry point. It holds global frontmatter and
imports the page files in presentation order:

```text
slides.md
pages/01-cover.md
pages/02-overview.md
...
pages/17-scope-and-reproducibility.md
```

Each file in `pages/` contains exactly one slide. Add, remove, or reorder pages
by changing the `src:` entries in `slides.md`.

## Run locally

```sh
cd presentation2
npm install
npm run dev
```

Open the URL printed by Slidev. Press `Space` or the arrow keys to advance,
`O` for the overview, and use presenter mode to see the notes.

## Build

```sh
npm run build
```

The static site is written to `presentation2/dist/`. PDF export is optional
and requires a Playwright Chromium installation:

```sh
npx playwright install chromium
npm run export
```

The figures in `public/` are copies of the accepted report figures under
`report/figures/`; the training-loop motivation figure on the architecture
opener comes from `report/training_to_network.png`. Headline values come
from the compact snapshots under `report/data/`.
