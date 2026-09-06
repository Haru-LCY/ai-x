---
theme: default
title: Bypass & Multicast in a Mesh NoC
info: |
  Lab 4 · Topic 3 (Microarchitecture: bypass + multicast) and Topic 4
  (trace-based traffic) · 8-minute presentation.
  Chunyu Liu and Boyan Pu.
author: Chunyu Liu and Boyan Pu
aspectRatio: 16/9
canvasWidth: 1280
transition: fade-out
colorSchema: dark
fonts:
  sans: IBM Plex Sans
  mono: IBM Plex Mono
defaults:
  layout: default
class: title-slide
---

<div class="titlewrap">

<div>

<div class="sec">Lab 4 · Topic 3 + Topic 4 · gem5 Garnet</div>

# <span class="accent">Bypass</span> &amp; <span class="accent">Multicast</span><br>in a Mesh NoC

<p class="sub">Two router-level microarchitecture mechanisms — express-link bypass and tree
multicast — built in gem5 Garnet and evaluated against matched baselines,
plus a real H100 trace-replay case study.</p>

<div class="who"><b>Chunyu Liu</b><i></i><b>Boyan Pu</b></div>

<div class="tags">
  <span class="tag cy">Topic 3 · Multicast 1 → N</span>
  <span class="tag am">Topic 3 · Express-link bypass</span>
  <span class="tag vi">Topic 4 · H100 trace replay</span>
</div>

</div>

<div>

<div class="svgwrap">
<svg viewBox="0 0 400 272" width="100%" role="img" aria-label="Mesh NoC with a multicast tree and express links">
  <!-- ordinary mesh links -->
  <g stroke="#23405c" stroke-width="2">
    <line x1="70" y1="55" x2="165" y2="55"/><line x1="165" y1="55" x2="260" y2="55"/><line x1="260" y1="55" x2="355" y2="55"/>
    <line x1="70" y1="120" x2="165" y2="120"/><line x1="165" y1="120" x2="260" y2="120"/><line x1="260" y1="120" x2="355" y2="120"/>
    <line x1="70" y1="185" x2="165" y2="185"/><line x1="165" y1="185" x2="260" y2="185"/><line x1="260" y1="185" x2="355" y2="185"/>
    <line x1="70" y1="250" x2="165" y2="250"/><line x1="165" y1="250" x2="260" y2="250"/><line x1="260" y1="250" x2="355" y2="250"/>
    <line x1="70" y1="55" x2="70" y2="120"/><line x1="70" y1="120" x2="70" y2="185"/><line x1="70" y1="185" x2="70" y2="250"/>
    <line x1="165" y1="55" x2="165" y2="120"/><line x1="165" y1="120" x2="165" y2="185"/><line x1="165" y1="185" x2="165" y2="250"/>
    <line x1="260" y1="55" x2="260" y2="120"/><line x1="260" y1="120" x2="260" y2="185"/><line x1="260" y1="185" x2="260" y2="250"/>
    <line x1="355" y1="55" x2="355" y2="120"/><line x1="355" y1="120" x2="355" y2="185"/><line x1="355" y1="185" x2="355" y2="250"/>
  </g>
  <!-- express links -->
  <g stroke="#ffb757" stroke-width="2.5" stroke-dasharray="6 5">
    <line x1="260" y1="55" x2="355" y2="120"/>
    <line x1="70" y1="250" x2="260" y2="250"/>
  </g>
  <!-- multicast tree -->
  <g stroke="#56d9ff" stroke-width="3">
    <line x1="165" y1="120" x2="70" y2="120"/>
    <line x1="165" y1="120" x2="165" y2="55"/>
    <line x1="165" y1="120" x2="165" y2="185"/>
    <line x1="165" y1="185" x2="260" y2="185"/>
    <line x1="260" y1="185" x2="355" y2="185"/>
  </g>
  <!-- routers -->
  <g fill="#0a1522" stroke="#54759a" stroke-width="2">
    <circle cx="70" cy="55" r="7"/><circle cx="260" cy="55" r="7"/><circle cx="70" cy="120" r="7"/>
    <circle cx="70" cy="185" r="7"/><circle cx="165" cy="185" r="7"/><circle cx="260" cy="185" r="7"/>
    <circle cx="355" cy="55" r="7"/><circle cx="355" cy="120" r="7"/><circle cx="165" cy="250" r="7"/>
    <circle cx="260" cy="250" r="7"/><circle cx="355" cy="250" r="7"/><circle cx="70" cy="250" r="7"/>
    <circle cx="260" cy="120" r="7"/><circle cx="355" cy="185" r="7"/><circle cx="165" cy="55" r="7"/>
  </g>
  <!-- multicast root and destinations -->
  <circle cx="165" cy="120" r="9" fill="#0a1522" stroke="#eef5fc" stroke-width="2.5"/>
  <circle cx="70" cy="120" r="7" fill="#56d9ff"/>
  <circle cx="165" cy="55" r="7" fill="#56d9ff"/>
  <circle cx="355" cy="185" r="7" fill="#56d9ff"/>
</svg>
</div>
<div class="legend">
  <span><i class="l-gray"></i>mesh XY</span>
  <span><i class="l-cyan"></i>multicast tree</span>
  <span><i class="l-amber"></i>express link</span>
</div>
<div class="cap">One 4×4 Mesh carries all three ideas: XY routes, a replicated multicast tree, express shortcuts.</div>

</div>

</div>

<!--
Timing 15 s. We are Chunyu Liu and Boyan Pu. Our lab covers Topic 3, bypass and multicast in a Mesh network-on-chip, and a Topic 4 trace case study.
-->

---

<div class="sec">Roadmap · 8 minutes</div>

# Four parts

<div class="body tight">

<div class="agenda">
  <div class="row">
    <div class="num cy">01</div>
    <div><b>Architecture</b><span>The baseline Garnet Mesh XY network, and where multicast and bypass plug into it.</span></div>
    <div class="t">≈ 2 min</div>
  </div>
  <div class="row">
    <div class="num am">02</div>
    <div><b>Implementation</b><span>How each mechanism is built, verified, and kept deadlock-free — plus the Topic 4 trace pipeline.</span></div>
    <div class="t">≈ 2 min</div>
  </div>
  <div class="row">
    <div class="num vi">03</div>
    <div><b>Evaluation</b><span>Paired comparisons against matched baselines — including the negative results.</span></div>
    <div class="t">≈ 3 min</div>
  </div>
  <div class="row">
    <div class="num rs">04</div>
    <div><b>Division of Labor</b><span>Who built what, and what we verified together.</span></div>
    <div class="t">≈ 30 s</div>
  </div>
</div>

</div>

<div class="take"><span class="lab">One rule throughout</span>Every number is a <b>paired comparison</b> — the new mechanism against an unmodified baseline with identical traffic, seeds and exit conditions.</div>

<!--
Timing 20 s. Four parts: architecture, implementation, evaluation, division of labor. The single rule to remember: every number you will see is a paired comparison against an untouched baseline.
-->

---

<div class="sec cy"><span class="n">01</span>Architecture</div>

# The layer we evaluate: gem5 Garnet, Mesh XY

<div class="body" style="grid-template-rows:auto 1fr;gap:12px">

<div>
  <div class="fig" style="height:296px"><img src="/training_to_network.png" alt="Training step lowers collectives onto the Mesh NoC" /></div>
  <div class="cap">Every training step lowers a collective into packets/flits on the Mesh NoC — traffic, latency and completion correctness of this layer is our subject.</div>
</div>

<div class="cards3">
  <div class="card cy">
    <span class="mark">PLATFORM</span>
    <h3>gem5 Garnet 2.0 NoC</h3>
    <p>Cycle-accurate router pipeline · wormhole flits (<code>HEAD / BODY / TAIL</code>) · virtual channels with credit-based flow control.</p>
  </div>
  <div class="card cy">
    <span class="mark">ROUTING</span>
    <h3>Deterministic XY</h3>
    <p>2D Mesh, along X then Y — a corner-to-corner packet costs 6 links and 7 router traversals. We study 2×2–8×8, so results stay hand-auditable.</p>
  </div>
  <div class="card gr">
    <span class="mark">DISCIPLINE</span>
    <h3>The baseline never moves</h3>
    <p><code>Mesh_XY</code> stays unmodified. Every mechanism arm runs against it with the <b>same</b> topology, workload, seeds and completion condition.</p>
  </div>
</div>

</div>

<div class="take cy"><span class="lab">Topic 3</span>Add two things to this network: <b>shortcut links</b> that cross intermediate nodes (bypass) and <b>one packet → N destinations</b> delivery (multicast).</div>

<!--
Timing 35 s. Here is where our work sits. Every training step produces gradients that must be all-reduced or broadcast; those collectives lower into packets and flits on the Mesh NoC, and the traffic, latency and completion correctness of exactly that layer is what we evaluate. Concretely we build on gem5's Garnet network: wormhole flits, virtual channels, credit flow control, deterministic XY routing. One corner-to-corner packet costs six links and seven router traversals. The baseline Mesh_XY is never modified - every new arm is paired against it.
-->

---

<div class="sec cy"><span class="n">01</span>Architecture · Multicast</div>

# Replicate inside the network, not at the source

<div class="body">

<div class="grid2 rev">

<div class="stack">

  <div class="card">
    <span class="mark">BASELINE · REPLICATED UNICAST</span>
    <h3>One packet per destination</h3>
    <div class="pkts"><span>dst A</span><span>dst B</span><span>dst C</span><span>dst D</span></div>
    <p>The NI injects N independent XY packets. Every shared route prefix carries the same payload N times.</p>
  </div>

  <div class="card cy">
    <span class="mark">NEW · TREE MULTICAST</span>
    <h3>One packet, replicated at branches</h3>
    <div class="bitmap"><b>HEAD</b><span>64-bit destination bitmap</span></div>
    <p>A single packet enters the network. Each router delivers locally if selected and copies flits <b>only onto branches that still lead to a destination</b>.</p>
  </div>

</div>

<div>

  <div class="fig" style="height:330px"><img src="/multicast_tree_flow.png" alt="Replicated unicast versus tree multicast on a 4x4 mesh" /></div>
  <div class="cap">4×4 Mesh, same destinations: replicated unicast (left) vs. bitmap tree multicast (right).</div>

</div>

</div>

</div>

<div class="take cy"><span class="lab">Key idea</span>The shared prefix is transmitted <b>once</b>; duplication happens <b>as late as possible</b> — at the branch routers. Each destination must receive exactly one copy.</div>

<!--
Timing 40 s. Multicast. The baseline lowers one logical multicast into N unicast packets, so shared prefixes carry the same payload repeatedly. Our design injects a single packet with a 64-bit destination bitmap. Routers deliver locally when selected and copy only onto branches that still contain destinations.
-->

---

<div class="sec cy"><span class="n">01</span>Architecture · Bypass</div>

# Express links: pay wire to skip routers

<div class="body">

<div class="grid2">

<div>

  <div class="fig" style="height:330px"><img src="/bypass_topology_oracle.png" alt="Diagonal and stride-2 express-link placements on a 4x4 mesh" /></div>
  <div class="cap">Diagonal (9 links) and stride-2 (16 links) placements on 4×4, with oracle-selected first hops.</div>

</div>

<div class="stack">

  <div class="card am">
    <span class="mark">MECHANISM</span>
    <h3>Extra links on top of the full Mesh</h3>
    <p>Every ordinary router and XY link is kept. We add <b>bidirectional express links</b> — diagonal <code>(x,y) ↔ (x±1, y±1)</code> or <b>stride-S</b> along a row/column. One traversal crosses the intermediate nodes.</p>
  </div>

  <div class="card am">
    <span class="mark">TWO PLACEMENTS ON 4×4</span>
    <h3>Diagonal vs. stride-2</h3>
    <p>Diagonal: 9 links, wire proxy 18, max radix 8 · Stride-2: 16 links, wire proxy 32, max radix 6.</p>
  </div>

  <div class="card">
    <span class="mark">THE TRADE</span>
    <h3>Fewer traversals, more hardware</h3>
    <p>Extra ports, longer wires, credit links — and a routing + deadlock problem that must be solved before any speedup counts.</p>
  </div>

</div>

</div>

</div>

<div class="take am"><span class="lab">Design constraint</span>A shortcut must win under a <b>hardware-relevant wire model</b>, not just hop count. That constraint shapes the routing design on the next slides.</div>

<!--
Timing 40 s. Bypass keeps the entire mesh and adds explicit express links: diagonal links, like the topic's example, and stride links along rows or columns. On 4x4 the diagonal placement costs 9 links and radix 8; stride-2 costs 16 links. The point of the study: a shortcut must pay for its wire, not just remove hops.
-->

---

<div class="sec am"><span class="n">02</span>Implementation · Multicast</div>

# Five mechanisms, one correctness contract

<div class="body">

<div class="grid2 rev">

<div class="steps cy" style="align-content:start">
  <div class="row"><em>1</em><div><b>Bitmap rides every flit</b><span>The 64-bit destination mask travels with <code>HEAD/BODY/TAIL</code>, so replication state survives serialization and backpressure.</span></div></div>
  <div class="row"><em>2</em><div><b>Pruned branch routing</b><span>The routing unit derives required output branches from the mask; branches with no destinations never see a flit.</span></div></div>
  <div class="row"><em>3</em><div><b>Replication at branch routers</b><span>A router with ≥ 2 selected branches copies each flit per branch; it ejects a local copy if its own bit is set.</span></div></div>
  <div class="row warn"><em>4</em><div><b>Atomic fanout</b><span>A flit advances only when <b>every</b> selected branch has VC credit — no drop, duplicate or reorder, even at 64 flits.</span></div></div>
  <div class="row"><em>5</em><div><b>Tail-driven release + tracker</b><span>Tail frees branch state and upstream credits; per-round expected/received bitmaps must match exactly, otherwise fatal.</span></div></div>
</div>

<div class="stack">

  <div class="card cy">
    <span class="mark">GATES M1–M5</span>
    <h3>Built in acceptance order</h3>
    <p>Unified request tracker → replicated-unicast baseline → subset pruning → multi-flit under backpressure → performance modes with warmup/cooldown.</p>
  </div>

  <div class="metric">
    <span class="v">208 / 208</span>
    <span class="k">paired correctness cases green</span>
    <span class="n">2×2 / 3×3 / 4×4 · all destination subsets · 1–64 flits · restricted VC/buffer configs</span>
  </div>

  <div class="card">
    <span class="mark">SCOPE</span>
    <h3>≤ 64 routers per bitmap</h3>
    <p>One bit per router in the destination mask — exactly covers the largest 8×8 network we evaluate.</p>
  </div>

</div>

</div>

</div>

<div class="take cy"><span class="lab">Contract</span>Completion = every destination in the set received the payload <b>exactly once</b>; duplicates, misses or misroutes abort the run. A timeout is a failure, never a result.</div>

<!--
Timing 45 s. Implementation of multicast, five mechanisms. The bitmap rides every flit, so state survives backpressure. Routing is pruned per branch. Routers copy flits at branches and eject locally. Fanout is atomic: a flit moves only when all branches have credit - that is what keeps 64-flit packets exact under pressure, and it is also the cause of the regressions you will see later. Gates M1 to M5, 208 of 208 correctness cases.
-->

---

<div class="sec am"><span class="n">02</span>Implementation · Bypass</div>

# New topology, offline oracle, provable deadlock freedom

<div class="body">

<div class="grid2 rev">

<div class="steps am" style="align-content:start">
  <div class="row"><em>1</em><div><b>Separate topology file</b><span><code>Mesh_Bypass</code> with <code>mode=none</code> must be graph-identical to <code>Mesh_XY</code> (gate G1); express + credit links are added explicitly, with stable names.</span></div></div>
  <div class="row"><em>2</em><div><b>Static routing oracle</b><span>Offline enumeration of all (src, dst): at most <b>one</b> express hop, taken at the source, accepted only if <code>1 + dist(landing, dst) &lt; dist(src, dst)</code>; the suffix is plain XY.</span></div></div>
  <div class="row"><em>3</em><div><b>Deadlock audit before simulation</b><span>Build the all-pairs channel-dependency graph; a placement is accepted only if it is a <b>DAG</b>. Cyclic placements are rejected — not "it didn't hang".</span></div></div>
  <div class="row"><em>4</em><div><b>Two wire models</b><span><b>Optimistic</b>: every express link costs 1 cycle (upper bound) · <b>Distance-scaled</b>: link and credit latency scale with Manhattan span. Every headline claim includes distance-scaled.</span></div></div>
</div>

<div class="stack">

  <div class="card am">
    <span class="mark">GATES G1–G10</span>
    <h3>Baseline equivalence → interaction</h3>
    <p>G1 graph equivalence, G2 link construction, G3 routing audit, G4–G7 function/backpressure/stats/full matrix, G8 performance, G9 cost-aware conclusion, G10 multicast interaction.</p>
  </div>

  <div class="metric am">
    <span class="v">7,680</span>
    <span class="k">gem5 runs in the G8 sweep</span>
    <span class="n">6,144 paired seed cases · 4 designs × 2 mesh sizes × 4 traffics × 16 loads × 3 seeds</span>
  </div>

</div>

</div>

</div>

<div class="take am"><span class="lab">Why so strict</span>Long links can create channel-dependency cycles that appear only under specific routes — so safety is <b>proved by construction</b>, and every shortcut is priced under both wire models.</div>

<!--
Timing 45 s. Bypass implementation. A separate topology file keeps the baseline untouched. A static oracle enumerates every source-destination pair and allows at most one source express hop, only when it strictly reduces remaining hops. Before any simulation, we build the channel-dependency graph and reject cyclic placements, which is the deadlock-safety argument. And we always price wires two ways; only the distance-scaled model counts for headline claims.
-->

---

<div class="sec am"><span class="n">02</span>Implementation · Topic 4</div>

# Trace-based traffic: a real H100 collective in Garnet

<div class="body">

<div class="grid2 rev">

<div class="steps vi" style="align-content:start">
  <div class="row"><em>1</em><div><b>Capture</b><span>NCCL all-reduce microbenchmark <b>executed on 8× NVIDIA H100</b> (PyTorch 2.8 / CUDA 12.8 / NCCL 2.27.3): 15 all-reduce events with sizes and release times.</span></div></div>
  <div class="row"><em>2</em><div><b>Scale into Garnet</b><span>Bytes and timestamps scaled by 1/1024 into a 4×4 Garnet Mesh; trace hashes and semantics recorded for provenance.</span></div></div>
  <div class="row"><em>3</em><div><b>Two lowerings, same traffic</b><span><b>Scalar</b>: 6,720 single-flit requests · <b>Tensor</b>: 15 multi-flit requests that keep each tensor whole.</span></div></div>
  <div class="row"><em>4</em><div><b>All-reduce inside the routers</b><span>Convergence tree: each router stores <code>parent</code>, <code>children</code>, <code>expected_fanin</code> from XY routes to the root — contributions merge upward, the result broadcasts back.</span></div></div>
</div>

<div class="stack">

  <div class="card vi">
    <span class="mark">VALIDATION</span>
    <h3>Identical work by construction</h3>
    <p>Both lowerings must inject the same <b>53,760</b> rank contributions and produce the same <b>147,840</b> router-generated flits — otherwise the run is rejected.</p>
  </div>

  <div class="card">
    <span class="mark">BROADCAST ARM</span>
    <h3>30-request replay</h3>
    <p>The same trace also replays as multicast broadcasts: 30 requests, 6,720 source flits, 210 deliveries — exercising the Topic 3 mechanism on real traffic.</p>
  </div>

</div>

</div>

</div>

<div class="take vi"><span class="lab">Question asked</span>With traffic held <b>identical</b>, what does the <b>representation</b> of a request — 6,720 scalar lanes vs. 15 tensor requests — change in a cycle-level NoC?</div>

<!--
Timing 35 s. Topic 4 is a trace case study. We executed an NCCL all-reduce microbenchmark on eight H100s, scaled the trace into Garnet, and lowered it two ways: 6,720 scalar single-flit requests versus 15 multi-flit tensor requests, reduced inside the routers on a convergence tree. Validation holds the injected work identical, so any difference is purely representation.
-->

---

<div class="sec vi"><span class="n">03</span>Evaluation · Methodology</div>

# Everything is paired, every arm is matched

<div class="body">

<div class="grid2 rev">

<div class="stack">

  <div class="card gr">
    <span class="mark">PAIRED CONTRACT</span>
    <h3>Same everything but the mechanism</h3>
    <p>Same topology size, source, <b>destination sequence</b>, packet size, injection schedule, background traffic, seed and completion condition. A sim-cycle timeout is a <b>failure</b>, never a result.</p>
  </div>

  <div class="card">
    <span class="mark">METRICS KEPT SEPARATE</span>
    <h3>Three different claims</h3>
    <p><b>Link-flit traffic</b> — structural · <b>Completion latency</b> — implemented system · <b>Throughput &amp; wire cost</b> — workload- and hardware-dependent.</p>
  </div>

</div>

<div>

  <table class="tbl">
    <thead><tr><th>Study</th><th>Arms (new vs. baseline)</th><th class="r">Paired scale</th></tr></thead>
    <tbody>
      <tr><td>Multicast</td><td>Tree bitmap vs. replicated unicast</td><td class="num">162 pairs · 324 runs</td></tr>
      <tr><td>Bypass</td><td>4 express designs vs. plain Mesh</td><td class="num">6,144 pairs · 7,680 runs</td></tr>
      <tr><td>Interaction</td><td>2×2 factorial: mode × topology</td><td class="num">416 pairs · 624 runs</td></tr>
      <tr><td>Trace replay</td><td>Tensor vs. scalar · bypass vs. XY</td><td class="num">30-req broadcast + all-reduce</td></tr>
    </tbody>
  </table>
  <div class="cap">Multicast: 4/8/16 destinations × 4 packet sizes × loads × backgrounds × 3 seeds · Bypass: 4 traffic patterns × 16 offered loads × 2 mesh sizes × 3 seeds, per design.</div>

</div>

</div>

</div>

<div class="take"><span class="lab">Why it matters</span>Identical inputs and seeds make each pair a controlled experiment — so a regression is a <b>property of the mechanism</b>, not noise.</div>

<!--
Timing 30 s. Methodology. Every study is paired: same destination sequence, seeds, packet sizes, exit conditions; timeouts are failures. Three claim types are kept separate - traffic, latency, throughput. Scale: 162 multicast pairs, 6,144 bypass pairs, 416 interaction pairs.
-->

---

<div class="sec vi"><span class="n">03</span>Evaluation · Multicast</div>

# Traffic saving is structural; throughput is not free

<div class="body" style="grid-template-rows:auto 1fr;gap:14px">

<div class="metrics">
  <div class="metric">
    <span class="v">−39.5%</span>
    <span class="k">mean internal-link flits</span>
    <span class="n">162 paired cases · median −41.2%</span>
  </div>
  <div class="metric">
    <span class="v">3.59×</span>
    <span class="k">median completion-latency speedup</span>
    <span class="n">mean 4.79× · min 1.2× (implemented system)</span>
  </div>
  <div class="metric warn">
    <span class="v">10 / 162</span>
    <span class="k">throughput regressions</span>
    <span class="n">all at 4 destinations · worst −18.2%</span>
  </div>
</div>

<div class="grid2">

<div>
  <div class="fig" style="height:250px"><img src="/traffic_reduction_by_group.png" alt="Internal-link flit reduction by destination count" /></div>
  <div class="cap">Link-flit saving vs. destination count — monotone in fanout.</div>
</div>

<div class="stack">
  <table class="tbl">
    <thead><tr><th>Destinations</th><th class="r">Link-flit saving</th><th class="r">Regressions</th></tr></thead>
    <tbody>
      <tr><td>4</td><td class="num amb">−26.2%</td><td class="num bad">10 / 54</td></tr>
      <tr><td>8</td><td class="num good">−39.2%</td><td class="num">0 / 54</td></tr>
      <tr><td>16</td><td class="num good">−53.1%</td><td class="num">0 / 54</td></tr>
    </tbody>
  </table>
  <div class="cap">Saving grows with fanout (pure tree sharing). Every regression sits in the smallest, most loaded group — atomic fanout couples the branches.</div>
</div>

</div>

</div>

<div class="take cy"><span class="lab">Reading</span>Link flits are the <b>structural</b> claim. Latency is an <b>implemented-system</b> number — collective flits use a dedicated router fast path. Regressions are reported, not hidden.</div>

<!--
Timing 45 s. Multicast results. Across 162 paired cases, tree multicast removes 39.5 percent of internal-link flits on average, growing from 26 percent at four destinations to 53 percent at sixteen - that is pure tree sharing and it is structural. Median completion latency improves 3.59x. But ten cases regress in throughput, all at four destinations: atomic fanout couples branches, and at small fanout there is little sharing to pay for it.
-->

---

<div class="sec vi"><span class="n">03</span>Evaluation · Bypass</div>

# Saved hops do not automatically become saved time

<div class="body">

<div class="grid2">

<div>
  <div class="fig" style="height:235px"><img src="/bypass_overall.png" alt="Latency speedup and throughput change for four bypass designs" /></div>
  <div class="cap">1,536 paired seed cases per design · 4 traffics × 16 loads × 2 mesh sizes × 3 seeds.</div>
</div>

<div class="stack">

  <table class="tbl">
    <thead><tr><th>Design</th><th class="r">Latency</th><th class="r">Slower cases</th></tr></thead>
    <tbody>
      <tr class="pick"><td>Diagonal · distance-scaled</td><td class="num amb">1.629×</td><td class="num amb">687 / 1536</td></tr>
      <tr><td>Diagonal · optimistic</td><td class="num">1.723×</td><td class="num">160 / 1536</td></tr>
      <tr><td>Stride · distance-scaled</td><td class="num bad">0.981×</td><td class="num bad">968 / 1536</td></tr>
      <tr><td>Stride · optimistic</td><td class="num">1.103×</td><td class="num">311 / 1536</td></tr>
    </tbody>
  </table>

  <div class="card am">
    <span class="mark">WHY</span>
    <h3>Hops vs. wire</h3>
    <p>Stride removes <b>more</b> router traversals (−15.5% vs. −2.8% for diagonal) but its 2× wire budget erases the win under distance-scaled wires. The mean also hides a wide distribution.</p>
  </div>

</div>

</div>

</div>

<div class="take am"><span class="lab">Honest reading</span>Diagonal bypass wins the <b>mean</b> with hardware-relevant wires — yet is still slower in <b>687 of 1,536</b> cases. Bypass is a <b>conditional</b> mechanism, not a general speedup.</div>

<!--
Timing 45 s. Bypass results. The headline: distance-scaled diagonal links give 1.629x mean latency speedup. But look at the third column - even the winning design is slower in 687 of 1536 paired cases. Stride removes more router traversals yet averages 0.981x under distance-scaled wires because it pays twice the wire budget. So we report bypass as conditional, not as a general win.
-->

---

<div class="sec vi"><span class="n">03</span>Evaluation · Interaction</div>

# The two mechanisms do not add up

<div class="body" style="grid-template-rows:auto auto;gap:16px">

<div class="duo">
  <div class="box cy">
    <div class="h">MULTICAST</div>
    <b>Removes duplicated work</b>
    <span>Shares route prefixes — most redundant traversals are already gone <b>before</b> any shortcut exists.</span>
  </div>
  <div class="box am">
    <div class="h">BYPASS</div>
    <b>Shortens long routes</b>
    <span>Helps distant or structured unicast traffic — when the wire cost of the shortcut is justified.</span>
  </div>
</div>

<div class="stat3">
  <div><span class="v">416</span><span class="k">paired interaction cases (2×2, 3×3, 4×4 · 2×2 factorial)</span></div>
  <div><span class="v">0.965×</span><span class="k">replicated unicast + distance-scaled bypass</span></div>
  <div><span class="v">0.988×</span><span class="k">tree multicast + distance-scaled bypass</span></div>
</div>

</div>

<div class="take"><span class="lab">Design decision</span>Our policy <b>rejects a shortcut that breaks a route prefix shared with another destination</b> — on the directed gate this costs 3,500 vs. 4,000 ticks. The H100 broadcast replay therefore uses <b>0 express flits by policy</b>, not by accident.</div>

<!--
Timing 30 s. Do the mechanisms compose? No. In the two-by-two factorial, distance-scaled bypass averages 0.965 with replicated unicast and 0.988 with tree multicast - both slightly below one. So we made multicast cost-aware: it refuses an express hop that would break a shared prefix, which is why the H100 replay uses zero express flits by policy.
-->

---

<div class="sec vi"><span class="n">03</span>Evaluation · Topic 4</div>

# A representation win, not a traffic win

<div class="body">

<div class="grid2">

<div>
  <div class="fig" style="height:250px"><img src="/tensor_measurement_comparison.png" alt="Scalar versus tensor replay measurement window" /></div>
  <div class="cap">Same trace, same traffic — only the request representation changes.</div>
</div>

<div class="stack">

  <div class="metric vi">
    <span class="v">4.728×</span>
    <span class="k">shorter measurement window</span>
    <span class="n">80,638,000 → 17,054,500 ticks</span>
  </div>

  <table class="tbl">
    <thead><tr><th>Held identical</th><th class="r">Both lowerings</th></tr></thead>
    <tbody>
      <tr><td>Rank contributions</td><td class="num">53,760</td></tr>
      <tr><td>Router-generated flits</td><td class="num">147,840</td></tr>
      <tr><td>Wire-flit distance</td><td class="num">94,080</td></tr>
      <tr><td>Express-link flits</td><td class="num">0 (both arms)</td></tr>
    </tbody>
  </table>

</div>

</div>

</div>

<div class="take vi"><span class="lab">Boundary</span>15 tensor requests vs. 6,720 scalar lanes remove <b>request serialization</b> — the bytes moved are the same. The all-reduce tree uses ordinary Mesh edges, so the topology arm is intentionally <b>neutral</b>. Not an H100 or training speedup.</div>

<!--
Timing 35 s. Topic 4 results. Keeping traffic byte-identical, the tensor lowering finishes the same trace with a 4.728x shorter measurement window - 80.6 million to 17 million ticks. Contributions, router flits and wire distance are identical, so this is purely a representation win: removing request serialization, not moving fewer bytes.
-->

---

<div class="sec">Conclusion</div>

# Three claims, kept separate

<div class="body">

<div class="cards3">
  <div class="card cy">
    <span class="mark">−39.5% LINK FLITS</span>
    <h3>Expose shared structure</h3>
    <p>Tree multicast reliably removes duplicated link traffic; the saving grows with fanout. Cost: atomic fanout can stall small, loaded groups.</p>
  </div>
  <div class="card am">
    <span class="mark">1.629× CONDITIONAL</span>
    <h3>Price every shortcut</h3>
    <p>Diagonal bypass wins the mean under distance-scaled wires; stride's larger wire budget erases its hop advantage. Regressions included.</p>
  </div>
  <div class="card vi">
    <span class="mark">4.728× WINDOW</span>
    <h3>Preserve request semantics</h3>
    <p>Tensor streaming removes scalar serialization while injecting exactly the same contributions and router flits.</p>
  </div>
</div>

</div>

<div class="take"><span class="lab">Design principle</span>Expose collective structure where it removes <b>demonstrable</b> network work · admit shortcuts only with <b>cost and safety checks</b> · report every mechanism against a <b>matched baseline</b> — negative cases included.</div>

<!--
Timing 25 s. Conclusion, three separate claims. Multicast removes duplicated work. Bypass helps only when its wire cost is paid for - a conditional mechanism. And preserving request semantics removes serialization without touching traffic.
-->

---

<div class="sec rs"><span class="n">04</span>Division of Labor</div>

# Built separately, integrated and verified together

<div class="body">

<div class="people">
  <div class="person">
    <div class="badge">CL</div>
    <div>
      <h3>Chunyu Liu</h3>
      <ul>
        <li>Tree multicast datapath + replicated-unicast baseline</li>
        <li>Bypass topologies, routing oracle, cost-aware policy</li>
        <li>Correctness matrices and paired performance sweeps</li>
        <li>H100 trace capture and broadcast replay</li>
      </ul>
    </div>
  </div>
  <div class="person vi">
    <div class="badge">BP</div>
    <div>
      <h3>Boyan Pu</h3>
      <ul>
        <li>Multi-flit tensor all-reduce datapath</li>
        <li>Replay contract, compiler and validator</li>
        <li>Backpressure and credit-conservation stress tests</li>
        <li>Tensor statistics and paired replay comparison</li>
      </ul>
    </div>
  </div>
</div>

</div>

<div class="take rs"><span class="lab">Shared</span>Branch integration · regression review · final quantitative snapshot · report and figure verification.</div>

<!--
Timing 20 s. Division of labor: Chunyu built multicast, bypass and the trace capture; Boyan built the tensor all-reduce datapath, its validator and the stress tests. Integration, regressions and the final snapshot were done together.
-->

---
class: end-slide
---

<div class="sec">gem5 Garnet · Topic 3 + Topic 4</div>

# Thank you

<p class="lines">Multicast shares duplicated work.<br>Bypass has to pay for distance.<br>Tensor streaming preserves the request.</p>

<div class="row">
  <span><b>−39.5%</b>link flits</span>
  <span><b>1.629×</b>conditional bypass</span>
  <span><b>4.728×</b>replay window</span>
</div>

<!--
Timing 5 s. Thank you - happy to take questions.
-->

---

<div class="sec">Backup</div>

# What exactly was compared?

<div class="body">

<table class="tbl">
  <thead><tr><th>Study</th><th>New mechanism</th><th>Matched baseline</th><th>Primary evidence</th></tr></thead>
  <tbody>
    <tr><td>Multicast</td><td>One bitmap packet, replicated at branch routers</td><td>4/8/16 independent XY packets, identical Mesh</td><td>Internal-link flits</td></tr>
    <tr><td>Bypass</td><td>Express links + static routing oracle</td><td>Same Mesh, no express links</td><td>Latency, throughput, wire cost</td></tr>
    <tr><td>Interaction</td><td>2×2 factorial: mode × topology</td><td>Each single-mechanism arm</td><td>Paired completion time</td></tr>
    <tr><td>Trace replay</td><td>15 multi-flit logical requests</td><td>6,720 serialized scalar lanes</td><td>End-to-end replay window</td></tr>
  </tbody>
</table>

<div class="formulas">
  <span>S_L = L_base / L_new</span>
  <span>R_F = 1 − F_new / F_base</span>
  <span>I_Q = Q_new / Q_base − 1</span>
</div>

</div>

<div class="take"><span class="lab">Acceptance</span>A timeout is a <b>failure</b>, never a result. Paired runs share inputs, seeds and exit conditions; count identities are verified before numbers enter the report.</div>

---

<div class="sec">Backup</div>

# Where these results stop

<div class="body">

<div class="bounds">
  <div><b>Multicast</b><span>One 4×4 source placement (router 5); collective flits use a dedicated router fast path, so latency is not an isolated replication effect.</span></div>
  <div><b>Bypass</b><span>Wire cost is a latency and static-cost proxy — no area, power, repeaters or timing closure. The oracle minimizes hops, not modeled latency.</span></div>
  <div><b>Trace</b><span>An executed collective microbenchmark, not a full model trace; bytes and times are scaled by 1/1024, and rank values are deterministic test values.</span></div>
  <div><b>Tensor</b><span>No finite accumulator capacity and no modeled arithmetic pipeline latency.</span></div>
  <div><b>Overall</b><span>Cycle-level Garnet mechanism results — not NVLink/NVSwitch hardware or end-to-end training throughput.</span></div>
</div>

</div>
