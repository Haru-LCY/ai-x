---
theme: default
title: Collective Communication for Modern GPU Training in gem5 Garnet
info: |
  Lab 4 presentation by Chunyu Liu and Boyan Pu.
  Router-level multicast, express-link bypass, and tensor all-reduce.
author: Chunyu Liu and Boyan Pu
aspectRatio: 16/9
canvasWidth: 1440
fonts:
  sans: Inter
  mono: JetBrains Mono
highlighter: shiki
lineNumbers: false
download: true
exportFilename: lab4-ai-collectives
transition: fade-out
mdc: true
class: title-slide
---

<div class="course">Lab 4 · Interconnection Networks</div>

# Collective Communication<br>for Modern GPU Training

<p class="subtitle">Router-level multicast, express-link bypass, and streaming tensor all-reduce in gem5 Garnet</p>

<div style="display:flex; gap:10px; margin-top:28px">
  <span class="tag">SHARE</span>
  <span class="tag orange-tag">SHORTCUT</span>
  <span class="tag green-tag">STREAM</span>
</div>

<div class="authors">
  <b>Chunyu Liu · Boyan Pu</b><br>
  Topic 3 + Topic 4 extension
</div>

<!--
Good morning. Our project asks one question: if GPU training repeatedly pays for collective communication, what structure should the NoC expose directly? We built and evaluated three mechanisms in gem5 Garnet: tree multicast, physical bypass links, and streaming tensor all-reduce.
Timing: 0:00–0:20.
-->

---

<div class="split-title">
  <div>
    <div class="eyebrow">Motivation</div>
    <h1>Collectives sit on the training critical path</h1>
  </div>
  <div class="section-no">01</div>
</div>

<div class="grid-2" style="grid-template-columns:1.05fr .95fr; align-items:center">
  <div>
    <p class="lead">Every training step alternates between local compute and a synchronization contract.</p>
    <div class="card" style="margin-top:20px">
      <div class="architecture-strip" style="grid-template-columns:1fr 30px 1fr; margin:0">
        <div class="node"><b>GPU ranks</b><span>produce gradients</span></div>
        <div class="arrow">→</div>
        <div class="node"><b>Collective</b><span>broadcast / all-reduce</span></div>
      </div>
      <div style="text-align:center; color:#7a8696; font-size:24px; margin:4px">↓</div>
      <div class="node" style="background:#eff7fc; border:1px solid #b9d9ec; border-radius:12px; padding:13px; text-align:center">
        <b style="color:#16243d">Mesh NoC router datapath</b>
      </div>
    </div>
  </div>
  <div class="grid-3" style="grid-template-columns:1fr; gap:14px">
    <div class="card share">
      <h3>Share duplicated prefixes</h3>
      <p>Replicate a broadcast only where paths branch.</p>
    </div>
    <div class="card shortcut">
      <h3>Shortcut long routes</h3>
      <p>Use physical express links only when wire cost is justified.</p>
    </div>
    <div class="card stream">
      <h3>Stream tensor requests</h3>
      <p>Preserve multi-flit request boundaries instead of serializing lanes.</p>
    </div>
  </div>
</div>

<div class="footer-note">Evaluation layer: cycle-level Garnet traffic, latency, throughput, and completion correctness.</div>

<!--
The communication phase delays the next training step. We found three different kinds of structure to exploit: shared prefixes in one-to-many traffic, shorter physical routes, and tensor request boundaries. The key point is that these are separate opportunities, so each needs its own baseline and metric.
Timing: 0:20–0:55.
-->

---

<div class="split-title">
  <div>
    <div class="eyebrow">System architecture</div>
    <h1>Three mechanisms, one auditable simulator</h1>
  </div>
  <div class="section-no">02</div>
</div>

<div class="architecture-strip" style="margin-top:42px">
  <div class="node">
    <b>Workload</b>
    <span>Synthetic traffic + executed 8×H100 collective trace</span>
  </div>
  <div class="arrow">→</div>
  <div class="node" style="border-top:5px solid var(--blue)">
    <b>Network Interface</b>
    <span>Bitmap packets · tensor metadata · exact-value checks</span>
  </div>
  <div class="arrow">→</div>
  <div class="node" style="border-top:5px solid var(--orange)">
    <b>Garnet Router + links</b>
    <span>Branch replication · lane reduction · express ports</span>
  </div>
</div>

<div class="grid-3" style="margin-top:34px">
  <div class="card">
    <span class="tag">MULTICAST</span>
    <h3 style="margin-top:12px">One bitmap packet</h3>
    <p>Router-local branch state and atomic fanout under credit backpressure.</p>
  </div>
  <div class="card">
    <span class="tag orange-tag">BYPASS</span>
    <h3 style="margin-top:12px">One express first hop</h3>
    <p>Offline route table, then a deterministic XY suffix with a dependency audit.</p>
  </div>
  <div class="card">
    <span class="tag green-tag">ALL-REDUCE</span>
    <h3 style="margin-top:12px">One lane per flit</h3>
    <p>Per-lane fan-in at Routers, then tree broadcast with FIFO retry.</p>
  </div>
</div>

<div class="callout" style="margin-top:26px"><b>Comparison contract:</b> same topology, traffic, packet sequence, and seed within every pair.</div>

<!--
The implementation touches the workload, Network Interface, Router, routing logic, and physical topology. The NI creates bitmap or tensor metadata and checks exact delivery. Routers replicate multicast branches or merge tensor lanes. For bypass, the route table chooses at most one express first hop, then uses an audited XY suffix. Every performance comparison is paired with identical workload inputs.
Timing: 0:55–1:35.
-->

---

<div class="split-title">
  <div>
    <div class="eyebrow">Architecture + implementation</div>
    <h1>Share: replication moves into branch Routers</h1>
  </div>
  <div class="section-no">03</div>
</div>

<div class="grid-2" style="grid-template-columns:1.42fr .58fr; gap:26px; align-items:center">
  <div>
    <div class="image-frame" style="height:410px">
      <img src="/figures/multicast_tree_flow.png" alt="Replicated unicast compared with router-level tree multicast">
    </div>
    <p class="caption">Source Router 5; destinations {3, 5, 10, 15} on a 4×4 Mesh.</p>
  </div>
  <div>
    <div class="card share">
      <h3>Baseline</h3>
      <p>One physical packet per destination; common XY prefixes repeat.</p>
    </div>
    <div style="height:12px"></div>
    <div class="card share">
      <h3>Tree multicast</h3>
      <p>One 64-bit destination bitmap; copies appear only at selected branch Routers.</p>
    </div>
    <div style="height:12px"></div>
    <div class="callout">
      <b>Correctness rule</b><br>
      HEAD/BODY/TAIL advance only when <i>all</i> selected branches have output VC credit.
    </div>
  </div>
</div>

<!--
The naive baseline sends a complete packet to each destination. Our packet instead carries a destination bitmap. Each Router removes local destinations, computes outgoing branches, and replicates only there. Multi-flit branch state is retained until the tail. To keep copies consistent under backpressure, fanout is atomic: a flit advances only when every selected output has credit. That guarantees correctness, but it also creates a performance trade-off.
Timing: 1:35–2:15.
-->

---

<div class="split-title">
  <div>
    <div class="eyebrow">Evaluation · 162 paired cases</div>
    <h1>Multicast reliably removes traffic—not every stall</h1>
  </div>
  <div class="section-no">04</div>
</div>

<div class="metric-row" style="margin:12px 0 28px">
  <div class="metric">
    <div class="value">39.51%</div>
    <div class="label">mean internal-link flit reduction</div>
  </div>
  <div class="metric">
    <div class="value">4.790×</div>
    <div class="label">mean packet-latency speedup</div>
  </div>
  <div class="metric orange-metric">
    <div class="value">10 / 162</div>
    <div class="label">throughput regressions; worst −18.24%</div>
  </div>
</div>

<div class="grid-2" style="grid-template-columns:.9fr 1.1fr; gap:42px">
  <div>
    <h3>Traffic saving grows with fanout</h3>
    <div class="bar-list" style="margin-top:22px">
      <div class="bar-row"><div class="bar-label">4 destinations</div><div class="bar-track"><div class="bar-fill" style="width:49%"></div></div><div class="bar-value">26.19%</div></div>
      <div class="bar-row"><div class="bar-label">8 destinations</div><div class="bar-track"><div class="bar-fill" style="width:74%"></div></div><div class="bar-value">39.22%</div></div>
      <div class="bar-row"><div class="bar-label">16 destinations</div><div class="bar-track"><div class="bar-fill" style="width:100%"></div></div><div class="bar-value">53.13%</div></div>
    </div>
  </div>
  <div class="callout orange-callout" style="align-self:start; margin-top:4px">
    <b>Why can less traffic still lose throughput?</b><br><br>
    Atomic fanout couples fast and blocked branches. All ten regressions occur in four-destination cases, concentrated in longer, loaded requests.
  </div>
</div>

<p class="small muted" style="margin-top:34px">Matrix dimensions: 4×4 Mesh · fanout {4, 8, 16} · packet size {1, 4, 16 flits} · multiple traffic/load conditions.</p>

<!--
Across 162 paired cases, multicast removes 39.51 percent of internal-link flits on average, and the saving rises monotonically with fanout. Latency improves in every pair. Throughput is more nuanced: ten cases regress, all at fanout four. This is not contradictory. The tree performs less total link work, but atomic fanout lets one blocked branch hold the others. So traffic reduction is structural; throughput remains workload dependent.
Timing: 2:15–2:55.
-->

---

<div class="split-title">
  <div>
    <div class="eyebrow">Architecture + implementation</div>
    <h1>Shortcut: add links, but make every route auditable</h1>
  </div>
  <div class="section-no">05</div>
</div>

<div class="grid-2" style="grid-template-columns:1.28fr .72fr; gap:30px; align-items:center">
  <div>
    <div class="image-frame" style="height:405px">
      <img src="/figures/bypass_topology_oracle.png" alt="Diagonal and stride express-link topologies">
    </div>
    <p class="caption">Orange: installed express candidates · Blue: deterministic XY suffix.</p>
  </div>
  <div>
    <div class="flow" style="flex-direction:column">
      <div class="step"><b>1 · Build candidates</b><span>Diagonal or stride physical links</span></div>
      <div class="chev">↓</div>
      <div class="step"><b>2 · Select one first hop</b><span>Only if remaining Manhattan distance shrinks</span></div>
      <div class="chev">↓</div>
      <div class="step"><b>3 · Audit dependencies</b><span>Accept only an acyclic channel-dependency graph</span></div>
      <div class="chev">↓</div>
      <div class="step"><b>4 · Follow XY suffix</b><span>Deterministic path after the shortcut</span></div>
    </div>
  </div>
</div>

<!--
Bypass adds physical diagonal or stride links. Before simulation, a route-table builder considers every source-destination pair and records at most one express first hop when it reduces the remaining Manhattan distance. The rest of the route is deterministic XY. We then build the channel-dependency graph and accept only acyclic placements. This makes the shortcut deadlock-safe and auditable, instead of relying on an opaque adaptive choice.
Timing: 2:55–3:40.
-->

---

<div class="split-title">
  <div>
    <div class="eyebrow">Evaluation · 6,144 paired seed cases</div>
    <h1>Wire cost decides whether fewer hops are valuable</h1>
  </div>
  <div class="section-no">06</div>
</div>

<table class="comparison" style="margin-top:22px">
  <thead>
    <tr><th>Express design</th><th>Latency speedup</th><th>Throughput change</th><th>Aggregate traversal reduction</th></tr>
  </thead>
  <tbody>
    <tr><td><b>Diagonal · distance-scaled</b></td><td class="best">1.629×</td><td class="best">+6.41%</td><td>−2.82%*</td></tr>
    <tr><td>Diagonal · optimistic</td><td class="best">1.723×</td><td class="best">+10.61%</td><td>−7.03%*</td></tr>
    <tr><td><b>Stride · distance-scaled</b></td><td class="warn">0.981×</td><td class="warn">−1.94%</td><td class="best">+15.50%</td></tr>
    <tr><td>Stride · optimistic</td><td>1.103×</td><td>+3.68%</td><td>+10.10%</td></tr>
  </tbody>
</table>

<div class="grid-3" style="margin-top:28px">
  <div class="card shortcut"><h3>Diagonal wins latency</h3><p>Short links survive distance-scaled timing and improve contention behavior.</p></div>
  <div class="card shortcut"><h3>Stride wins hop count</h3><p>Longer links remove Router traversals, but wire latency and radix erase the gain.</p></div>
  <div class="card shortcut"><h3>Physical cost differs</h3><p>4×4: diagonal adds 9 links (wire proxy 18); stride adds 16 (wire proxy 32).</p></div>
</div>

<p class="tiny muted" style="margin-top:18px">*Aggregate traversals may rise when a faster design delivers more packets; read together with throughput. Each design: 1,536 paired cases across sizes, traffic patterns, packet lengths, loads, and seeds.</p>

<!--
The primary bypass sweep contains 1,536 paired cases per design. Distance-scaled diagonal links give the best hardware-oriented result: 1.629 times mean latency speedup and 6.41 percent throughput improvement. Stride links remove more Router traversals, but under distance-scaled wire timing they average a slight slowdown. The lesson is that hop reduction is not enough; wire span, added links, radix, and congestion determine whether the physical shortcut is useful.
Timing: 3:40–4:30.
-->

---

<div class="split-title">
  <div>
    <div class="eyebrow">Architecture + implementation</div>
    <h1>Stream: keep a tensor as one multi-flit request</h1>
  </div>
  <div class="section-no">07</div>
</div>

<div class="grid-2" style="grid-template-columns:1.3fr .7fr; gap:30px; align-items:center">
  <div>
    <div class="image-frame" style="height:414px">
      <img src="/figures/tensor_allreduce_pipeline.png" alt="Multi-flit tensor all-reduce datapath and replay lowering">
    </div>
  </div>
  <div>
    <div class="card stream">
      <h3>Per-flit identity</h3>
      <p><code>(collective_id, lane_id)</code> stays attached through reduction and broadcast.</p>
    </div>
    <div style="height:12px"></div>
    <div class="card stream">
      <h3>Backpressure-safe state</h3>
      <p>Per-Router lane table + pending-forward FIFO retries when output credit is unavailable.</p>
    </div>
    <div style="height:12px"></div>
    <div class="card stream">
      <h3>Exact completion</h3>
      <p>Every rank checks every lane value; residual lane/FIFO state fails the run.</p>
    </div>
  </div>
</div>

<!--
Our Topic 4 extension replaces a scalar all-reduce path with a true multi-flit tensor request. Each flit carries a lane ID. Routers key accumulation state by collective and lane, merge contributions on an XY convergence tree, and broadcast the result. If downstream credit is unavailable, a FIFO retains the forward rather than dropping or failing. At completion, every rank checks the exact value of every lane, and we assert that no collective state remains.
Timing: 4:30–5:15.
-->

---

<div class="split-title">
  <div>
    <div class="eyebrow">Executed 8×H100 trace replay</div>
    <h1>Same network work, 4.728× shorter replay window</h1>
  </div>
  <div class="section-no">08</div>
</div>

<div class="grid-2" style="grid-template-columns:.78fr 1.22fr; gap:44px; align-items:center">
  <div>
    <div class="metric green-metric" style="padding:30px">
      <div class="value" style="font-size:62px">4.728×</div>
      <div class="label" style="font-size:15px">measurement-window speedup</div>
    </div>
    <div class="metric-row" style="grid-template-columns:1fr 1fr; gap:12px; margin-top:12px">
      <div class="metric purple-metric"><div class="value" style="font-size:28px">6,720</div><div class="label">scalar requests</div></div>
      <div class="metric green-metric"><div class="value" style="font-size:28px">15</div><div class="label">tensor requests</div></div>
    </div>
  </div>
  <div>
    <div class="bar-list">
      <div class="bar-row" style="grid-template-columns:150px 1fr 120px">
        <div class="bar-label"><b>Scalar lanes</b></div>
        <div class="bar-track" style="height:24px"><div class="bar-fill" style="width:100%; background:linear-gradient(90deg,#7950b8,#a98bd6)"></div></div>
        <div class="bar-value">80.638 M ticks</div>
      </div>
      <div class="bar-row" style="grid-template-columns:150px 1fr 120px">
        <div class="bar-label"><b>Tensor stream</b></div>
        <div class="bar-track" style="height:24px"><div class="bar-fill" style="width:21.15%; background:linear-gradient(90deg,#26956b,#65c49d)"></div></div>
        <div class="bar-value">17.055 M ticks</div>
      </div>
    </div>
    <div class="callout green-callout" style="margin-top:35px">
      <b>Controlled comparison</b><br>
      Both lowerings perform 53,760 rank-contribution flits and 147,840 Router flits. The gain comes from request representation and completion scheduling—not less network work.
    </div>
    <p class="small muted" style="margin-top:22px">15 measurement-phase all-reduce events · 1/1024 byte/time scale · 16-byte flits · Mesh XY and Mesh Bypass agree.</p>
  </div>
</div>

<!--
We replayed 15 measurement-phase all-reduces from an executed eight-H100 NCCL microbenchmark. The old lowering serializes 6,720 scalar lanes; the new lowering retains 15 multi-flit requests. The replay window falls from 80.638 to 17.055 million ticks, a 4.728 times speedup. Importantly, both execute exactly 53,760 contribution flits and 147,840 Router flits, so this isolates request representation and scheduling rather than claiming less physical traffic.
Timing: 5:15–6:00.
-->

---

<div class="split-title">
  <div>
    <div class="eyebrow">Correctness + reproducibility</div>
    <h1>Performance numbers are gated by invariants</h1>
  </div>
  <div class="section-no">09</div>
</div>

<div class="grid-2" style="grid-template-columns:1.1fr .9fr; gap:42px">
  <div>
    <table class="comparison">
      <thead><tr><th>Gate</th><th>Accepted cases</th><th>Status</th></tr></thead>
      <tbody>
        <tr><td>Legacy collective regression</td><td>11</td><td class="best">PASS</td></tr>
        <tr><td>Multicast correctness matrix</td><td>208</td><td class="best">PASS</td></tr>
        <tr><td>Tensor size/topology/root matrix</td><td>14</td><td class="best">PASS</td></tr>
        <tr><td>Tensor backpressure matrix</td><td>32</td><td class="best">PASS</td></tr>
        <tr><td>H100 broadcast / tensor / paired</td><td>30 / 15 / 2</td><td class="best">PASS</td></tr>
      </tbody>
    </table>
  </div>
  <div>
    <div class="card">
      <h3>Fail-fast contracts</h3>
      <ul class="small" style="padding-left:18px; color:#4d5968">
        <li>exact destination deliveries</li>
        <li>exact per-lane reduced values</li>
        <li>no duplicate / wrong-lane / incomplete request</li>
        <li>credit conservation and zero residual state</li>
        <li>provenance, trace hashes, and paired run inputs</li>
      </ul>
    </div>
    <div class="callout" style="margin-top:18px"><b>Seven-stage full gate: 7 / 7 PASS</b></div>
  </div>
</div>

<p class="small muted" style="margin-top:28px">Retained artifacts: compact CSV/JSON snapshots, generated figures, run manifests, trace hashes, and exact reproduction commands.</p>

<!--
Correctness is part of the architecture, not an afterthought. The complete seven-stage gate passes. We test multicast delivery, tensor sizes and roots, one-credit-depth backpressure, exact arithmetic, replay completeness, credit conservation, and zero residual state. The report keeps compact accepted data, manifests, trace hashes, and reproduction commands. This matters because a fast collective with one missing lane is simply wrong.
Timing: 6:00–6:35.
-->

---

<div class="split-title">
  <div>
    <div class="eyebrow">Interpretation boundary</div>
    <h1>What the evidence supports—and what it does not</h1>
  </div>
  <div class="section-no">10</div>
</div>

<div class="grid-2" style="gap:30px; margin-top:26px">
  <div class="card" style="border-top:5px solid var(--green)">
    <h3>Supported by the experiments</h3>
    <ul class="small" style="padding-left:18px; color:#4d5968">
      <li>tree replication removes duplicated Mesh link work</li>
      <li>distance-scaled diagonal shortcuts improve the tested sweep</li>
      <li>multi-flit tensor replay removes scalar request serialization</li>
      <li>all mechanisms satisfy their completion contracts</li>
    </ul>
  </div>
  <div class="card" style="border-top:5px solid var(--orange)">
    <h3>Not claimed</h3>
    <ul class="small" style="padding-left:18px; color:#4d5968">
      <li>area, energy, repeater, or timing-closure results</li>
      <li>NVLink/NVSwitch or end-to-end model speedup</li>
      <li>full training trace fidelity—the H100 source is a microbenchmark</li>
      <li>bounded hardware tensor tables or arithmetic pipeline latency</li>
    </ul>
  </div>
</div>

<div class="callout orange-callout" style="margin-top:28px">
  <b>Important neutral result:</b> the H100 collective placement selects zero express hops. Mesh XY and Mesh Bypass therefore match—adding links does not imply every workload uses them.
</div>

<!--
We keep the claims narrow. These are cycle-level Garnet results, not silicon area or power, NVLink performance, or end-to-end training speedup. The H100 input is an executed collective microbenchmark scaled by 1 over 1024, not a full model trace. Also, the H100 collective tree selects zero express hops, so the two topology arms match. That neutral result is useful: merely adding links does not help a workload whose routes do not select them.
Timing: 6:35–7:05.
-->

---

<div class="split-title">
  <div>
    <div class="eyebrow">Division of labor</div>
    <h1>Two owners, shared integration</h1>
  </div>
  <div class="section-no">11</div>
</div>

<div class="grid-2" style="gap:30px; margin-top:30px">
  <div class="card" style="border-top:6px solid var(--blue); padding:26px">
    <div class="tag">CHUNYU LIU</div>
    <h2 style="margin:16px 0 10px">Multicast + bypass</h2>
    <p>Implementation, correctness checks, H100 trace capture, optimization, performance sweep, and analysis.</p>
  </div>
  <div class="card" style="border-top:6px solid var(--green); padding:26px">
    <div class="tag green-tag">BOYAN PU</div>
    <h2 style="margin:16px 0 10px">Tensor all-reduce</h2>
    <p>Datapath, replay contract and validator, backpressure stress tests, tensor statistics, and paired evaluation.</p>
  </div>
</div>

<div class="architecture-strip" style="grid-template-columns:1fr 50px 1fr 50px 1fr; margin-top:38px">
  <div class="node"><b>Integrate</b><span>merge mechanisms and runners</span></div>
  <div class="arrow">→</div>
  <div class="node"><b>Review</b><span>cross-check invariants and regressions</span></div>
  <div class="arrow">→</div>
  <div class="node"><b>Reproduce</b><span>rerun final snapshot and report</span></div>
</div>

<p class="small muted" style="text-align:center; margin-top:12px">Both authors jointly performed integration, regression review, final reruns, and report verification.</p>

<!--
Chunyu owned multicast and bypass, including implementation, trace capture, optimization, and evaluation. Boyan owned tensor all-reduce, including the datapath, replay contract, validator, backpressure tests, and statistics. We jointly integrated the branches, reviewed regressions, reran the final artifact snapshot, and verified the report.
Timing: 7:05–7:30.
-->

---
class: takeaway-slide
---

<div class="eyebrow" style="color:#78d5ef">Conclusion</div>

# Expose useful structure—then measure its cost

<div class="metric-row" style="margin:38px 0 34px">
  <div class="metric">
    <div class="value">39.51%</div>
    <div class="label">less internal-link traffic with tree multicast</div>
  </div>
  <div class="metric">
    <div class="value">1.629×</div>
    <div class="label">latency speedup with distance-scaled diagonal bypass</div>
  </div>
  <div class="metric">
    <div class="value">4.728×</div>
    <div class="label">shorter H100 replay window with tensor streaming</div>
  </div>
</div>

<div class="grid-3" style="color:rgba(255,255,255,.82)">
  <p><b style="color:#fff">Share</b><br><span class="small">where common route prefixes remove real link work.</span></p>
  <p><b style="color:#fff">Shortcut</b><br><span class="small">only when wire cost and traffic make the hop valuable.</span></p>
  <p><b style="color:#fff">Stream</b><br><span class="small">with explicit request units and completion invariants.</span></p>
</div>

<p style="font-size:22px; margin-top:36px; color:#78d5ef"><b>Thank you · Questions?</b></p>

<!--
To conclude: multicast robustly removes duplicated traffic, bypass helps only when physical cost and route structure align, and tensor streaming removes scalar serialization while preserving identical network work. Our design principle is to expose collective structure where it removes measurable work, but keep cost models, baselines, and completion contracts explicit. Thank you.
Timing: 7:30–8:00.
-->
