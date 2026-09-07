---
theme: default
title: Collective-Aware Router Microarchitecture in gem5 Garnet
info: |
  Lab 4 · Topic 3 (bypass and multicast) and Topic 4 (trace-based traffic).
  Chunyu Liu and Boyan Pu.
author: Chunyu Liu and Boyan Pu
aspectRatio: 16/9
canvasWidth: 1280
transition: fade-out
colorSchema: light
fonts:
  sans: Gill Sans MT
  mono: IBM Plex Mono
defaults:
  layout: default
class: title-slide
---

<div class="titlewrap single">

<div>

<!-- <div class="sec">Lab 4 · Topic 3 + Topic 4 · gem5 Garnet</div> -->

# Collective-Aware Router<br>Microarchitecture in gem5 Garnet

<p class="sub">Multicast, express-link bypass, and tensor all-reduce evaluated against matched baselines.</p>

<div class="who"><b>Chunyu Liu</b><i></i><b>Boyan Pu</b></div>

<!-- <div class="tags">
  <span class="tag cy">Tree multicast</span>
  <span class="tag am">Pressure-aware bypass</span>
  <span class="tag vi">H100 tensor replay</span>
</div> -->

</div>

</div>

<!--
Timing 10 s. We report three related mechanisms: router-side multicast, pressure-aware express-link bypass, and trace-driven tensor all-reduce. The common thread is preserving collective structure inside the network.
-->

---

# Overview

<p class="lede">Four paired studies, in report order.</p>

<div class="body tight">

<div class="agenda">
  <div class="row">
    <div class="num">01</div>
    <div><b>Common substrate and metrics</b><span>What is paired, what is counted, and what each comparison does not claim.</span></div>
    <!-- <div class="t">1 min</div> -->
  </div>
  <div class="row">
    <div class="num cy">02</div>
    <div><b>Tree multicast</b><span>Replicate at pruned-tree branches; validate exact delivery; evaluate 4×4 and 8×8.</span></div>
    <!-- <div class="t">2 min</div> -->
  </div>
  <div class="row">
    <div class="num am">03</div>
    <div><b>Pressure-aware express-link bypass</b><span>Distance-scaled stride links, multi-hop DOR routes, and conservative admission.</span></div>
    <!-- <div class="t">2 min</div> -->
  </div>
  <div class="row">
    <div class="num vi">04</div>
    <div><b>H100 tensor all-reduce</b><span>Replay measured collectives; compare scalar-lane and event-level representations.</span></div>
    <!-- <div class="t">2 min</div> -->
  </div>
</div>

</div>

<!-- <div class="take"><span class="lab">Rule</span>Every performance number is paired: the proposed arm and its baseline use the same workload realization, packet size, load, and seed.</div> -->

<!--
Timing 20 s. The presentation follows the report. First the common methodology, then multicast, bypass, and the H100 trace extension. The pairing rule applies to all three studies.
-->

---

# Architecture

<p class="lede">The common substrate is gem5 Garnet: a cycle-level Mesh router with deterministic XY routing. Each mechanism changes one part of that router and is compared with a matched baseline.</p>

<div class="body">

<div class="grid2">

<div>

  <div class="fig" style="height:295px"><img src="/training_to_network.png" alt="GPU training collectives lowered onto a Mesh network-on-chip" /></div>
  <div class="cap">Training synchronization maps collective operations onto packets and flits; this work evaluates that Router layer.</div>

</div>

<div class="stack">

  <div class="card gr">
    <span class="mark">SUBSTRATE</span>
    <h3>gem5 v23.0.0.1 / Garnet</h3>
    <p>Cycle-level router pipelines, wormhole flits, virtual channels, and credit-based flow control. Plain Mesh and collective trees use deterministic X-first XY routing.</p>
  </div>

  <div class="card gr">
    <span class="mark">PAIRED METRICS</span>
    <h3>Traffic, latency, throughput</h3>
    <p>Internal-link flit reduction is additive; paired latency uses <code>L_base/L_new</code>; logical throughput uses <code>Q_new/Q_base−1</code>. Regressions remain in the inventory.</p>
  </div>

  <div class="card gr">
    <span class="mark">BASELINES</span>
    <h3>One changed variable per study</h3>
    <p>Tree multicast compares to replicated unicast. Bypass compares to plain Mesh XY. Tensor replay compares event-level packets with scalar-lane rounds.</p>
  </div>

</div>

</div>

</div>

<div class="take"><span class="lab">Scope</span>These are network-layer results. They are not end-to-end GPU training speedups.</div>

<!--
Timing 30 s. All experiments use gem5 Garnet and deterministic XY routing. Each study changes one mechanism and keeps workload realization, packet size, load, and seed paired. We keep traffic, latency, and throughput claims separate.
-->

---

# Tree multicast

<p class="lede">Replicate inside pruned-tree branches.</p>

<div class="body">

<div class="grid2 rev">

<div class="stack">

  <div class="card">
    <span class="mark">BASELINE</span>
    <h3>Replicated unicast</h3>
    <p>The NI injects one packet per remote destination and records a selected local destination. Shared path prefixes carry the same payload repeatedly.</p>
  </div>

  <div class="card cy">
    <span class="mark">PROPOSED</span>
    <h3>One bitmap packet</h3>
    <p>A 64-bit destination bitmap travels in the head flit. Each Router computes only the child branches that still lead to a destination and delivers locally when selected.</p>
  </div>

  <div class="card cy">
    <span class="mark">TRADEOFF</span>
    <h3>Exact, but synchronized</h3>
    <p>Fanout is atomic: a flit advances only after every selected output VC has credit. This preserves multi-flit delivery, but a blocked branch can hold the others.</p>
  </div>

</div>

<div>

  <div class="figpair">
    <div>
      <div class="fig" style="height:285px"><img src="/multicast_baseline_4x4.png" alt="Replicated-unicast baseline on a four-by-four mesh" /></div>
      <div class="cap"><b>(a)</b> Replicated-unicast baseline</div>
    </div>
    <div>
      <div class="fig" style="height:285px"><img src="/multicast_tree_4x4.png" alt="Proposed pruned-tree multicast path on a four-by-four mesh" /></div>
      <div class="cap"><b>(b)</b> Proposed tree multicast</div>
    </div>
  </div>
  <div class="cap">Illustrative 4×4 multicast baseline and proposed path.</div>

</div>

</div>

</div>

<div class="take cy"><span class="lab">Correctness contract</span>Every destination receives the complete packet exactly once, in flit order, with no missing or duplicate delivery.</div>

<!--
Timing 35 s. The baseline repeats a packet for every destination. Tree multicast sends one packet with a destination bitmap. Routers prune the tree and copy only on useful branches. Atomic fanout is necessary for exact multi-flit delivery, but it couples branch progress.
-->

---

# Multicast implementation

<p class="lede">Two-phase allocation, then validation.</p>

<div class="body">

<div class="grid2 rev">

<div class="steps cy" style="align-content:start">

  <div class="row"><em>1</em><div><b>Head computes the pruned tree</b><span>The bitmap selects child branches; branches with no destination never receive a flit.</span></div></div>
  <div class="row"><em>2</em><div><b>Branch state commits atomically</b><span>The Router allocates all required output VCs together; body and tail flits reuse those VCs.</span></div></div>
  <div class="row"><em>3</em><div><b>Tail releases the reservation</b><span>Per-round expected and received delivery sets must match exactly before the case is accepted.</span></div></div>

</div>

<div class="stack">

  <div class="metric">
    <span class="v">240 / 240</span>
    <span class="k">functional executions pass</span>
    <span class="n">120 mode-matched comparisons · 2×2–8×8 · two implementations · four packet sizes</span>
  </div>

  <div class="metric cy">
    <span class="v">324 + 108</span>
    <span class="k">paired performance cases</span>
    <span class="n">324 common cross-topology pairs · 108 additional 8×8 scale-out pairs</span>
  </div>

  <div class="card">
    <span class="mark">DOMAIN BOUND</span>
    <h3>64 routers per bitmap</h3>
    <p>The compact mask covers the largest evaluated 8×8 network exactly.</p>
  </div>

</div>

</div>

</div>

<div class="take cy"><span class="lab">Validated properties</span>Payload values, destination sets, flit ordering, and completion under backpressure.</div>

<!--
Timing 30 s. Implementation is a two-phase allocation. The head computes useful branches; branch VCs commit together; body and tail reuse them. Validation covers 240 executions, while performance uses 324 common pairs plus 108 scale-out pairs.
-->

---

# Multicast results

<p class="lede">Common-fanout gains, with regressions retained.</p>

<div class="body">

<div class="grid2">

<div>

  <div class="fig" style="height:275px"><img src="/traffic_reduction_by_group.png" alt="Internal-link flit reduction by topology and destination count" /></div>
  <div class="cap">4×4 and 8×8 common-fanout results are reported separately; fanout 32 and 64 are scale-out only.</div>

</div>

<div class="stack">

  <table class="tbl">
    <thead><tr><th>Mesh</th><th class="r">Link-flit red.</th><th class="r">Latency</th><th class="r">Throughput</th><th class="r">Regress.</th></tr></thead>
    <tbody>
      <tr><td>4×4 · 162 pairs</td><td class="num">39.51%</td><td class="num">3.638×</td><td class="num">+190.89%</td><td class="num bad">10</td></tr>
      <tr><td>8×8 · 162 pairs</td><td class="num">34.95%</td><td class="num">3.472×</td><td class="num">+208.34%</td><td class="num good">0</td></tr>
    </tbody>
  </table>

  <div class="cap" style="text-align:left">Latency is geometric mean; link-flit reduction and throughput are arithmetic means. Medians: 41.18%/29.63% traffic and 3.588×/2.667× latency.</div>

  <div class="card cy">
    <span class="mark">WHY THE 4×4 CASES SLOW</span>
    <h3>Atomic branch coupling</h3>
    <p>All ten regressions are fanout-4 cases; the worst is <b>−18.24%</b>. A congested output can hold the reservation while other branches wait.</p>
  </div>

</div>

</div>

</div>

<div class="take cy"><span class="lab">Reading</span>Link-flit saving is structural. Latency includes the dedicated Router datapath. Throughput exposes synchronization cost rather than being folded into a single score.</div>

<!--
Timing 45 s. At common fanouts, 4x4 removes 39.51 percent of internal-link flits and 8x8 removes 34.95 percent. Latency speedups are 3.638x and 3.472x. Mean throughput improves in both studies, but 4x4 has ten fanout-four regressions caused by atomic branch coupling; 8x8 has none.
-->

---

# Multicast scale-out

<p class="lede">Larger fanouts expose more shared prefixes.</p>

<div class="body" style="grid-template-rows:auto 1fr;gap:14px">

<div class="metrics">
  <div class="metric cy">
    <span class="v">−62.41%</span>
    <span class="k">link flits at fanout 32</span>
    <span class="n">8×8 scale-out study</span>
  </div>
  <div class="metric cy">
    <span class="v">11.25×</span>
    <span class="k">geometric-mean latency speedup</span>
    <span class="n">fanout 32</span>
  </div>
  <div class="metric cy">
    <span class="v">−75.39%</span>
    <span class="k">link flits at fanout 64</span>
    <span class="n">8×8 scale-out study</span>
  </div>
  <div class="metric cy">
    <span class="v">21.62×</span>
    <span class="k">geometric-mean latency speedup</span>
    <span class="n">fanout 64</span>
  </div>
</div>

<div>

  <div class="fig" style="height:260px"><img src="/latency_speedup_by_group.png" alt="Multicast latency speedup by topology, fanout, and packet size" /></div>
  <div class="cap">Scale-out means: +895.54% throughput at fanout 32 and +1,888.29% at fanout 64. These groups are not pooled with the common-fanout mean.</div>

</div>

</div>

<div class="take cy"><span class="lab">Interpretation</span>The gain grows because more destinations share prefixes. The scale-out numbers characterize 8×8; they are not a cross-topology average.</div>

<!--
Timing 30 s. The separate 8x8 scale-out study reaches 62.41 percent traffic reduction at fanout 32 and 75.39 percent at fanout 64. Latency speedups are 11.25x and 21.62x. We keep these groups separate from the common-fanout comparison.
-->

---

# Bypass topology

<p class="lede">Stride-2 links priced by wire span.</p>

<div class="body" style="grid-template-rows:auto 1fr;gap:14px">

<div class="grid2">

<div>

  <div class="fig" style="height:270px"><img src="/bypass_diagonal_4x4.png" alt="Phase-ordered diagonal bypass alternative on a 4 by 4 mesh" /></div>
  <div class="cap">Diagonal alternative: X*, diagonal*, then Y*.</div>

</div>

<div>

  <div class="fig" style="height:270px"><img src="/bypass_stride_4x4.png" alt="Proposed stride-2 bypass topology on a 4 by 4 mesh" /></div>
  <div class="cap">Primary design: repeated stride-2 hops while preserving DOR.</div>

</div>

</div>

<div class="cards3">
  <div class="card am">
    <span class="mark">MESH_BYPASS</span>
    <h3>Ordinary Mesh plus shortcuts</h3>
    <p>Bidirectional stride-2 links are appended; ordinary routers and XY links remain.</p>
  </div>
  <div class="card am">
    <span class="mark">CYCLE-AWARE TABLE</span>
    <h3>Multi-hop X then Y</h3>
    <p>Express latency scales with Manhattan span. An edge is selected only when it lowers the complete remaining path cost.</p>
  </div>
  <div class="card">
    <span class="mark">BASELINE</span>
    <h3>Plain Mesh XY</h3>
    <p>The comparator has fewer links, ports, VCs, and buffers. This is an added-resource comparison, not iso-area or iso-power.</p>
  </div>
</div>

</div>

<!--
Timing 40 s. Mesh_Bypass keeps the ordinary mesh and adds bidirectional stride-two links. A route-table builder may use multiple express hops in X and then Y, but only when the distance-scaled edge lowers the remaining path cost. The diagonal placement is an alternative, not the primary result.
-->

---

# Routing and safety

<p class="lede">Consult the table, then check pressure.</p>

<div class="body">

<div class="grid2 rev">

<div class="steps am" style="align-content:start">

  <div class="row"><em>1</em><div><b>Static, cycle-aware route</b><span>Every current-router/destination pair is materialized before simulation; exact-cost ties prefer the ordinary edge.</span></div></div>
  <div class="row"><em>2</em><div><b>Conservative fallback</b><span>Unordered traffic may return to monotonic XY when an express or landing output is blocked or materially more congested.</span></div></div>
  <div class="row"><em>3</em><div><b>Hotspot and long-packet guards</b><span>Epoch counters detect sustained destination skew; packets above 32 flits need express and landing credit headroom.</span></div></div>
  <div class="row"><em>4</em><div><b>Deadlock check by construction</b><span>All successive channel pairs form a graph that must have a topological order; runtime choices remain DOR-preserving.</span></div></div>

</div>

<div class="stack">

  <div class="metric am">
    <span class="v">1,536</span>
    <span class="k">matched performance pairs</span>
    <span class="n">768 per mesh · 4 traffics × 4 packet sizes × 16 loads × 3 seeds</span>
  </div>

  <div class="card am">
    <span class="mark">VALIDATION</span>
    <h3>5 / 8 / 14 cases</h3>
    <p>Route and dependency, traversal, and multi-flit/backpressure suites respectively.</p>
  </div>

  <div class="card">
    <span class="mark">PILOT DECISION</span>
    <h3>Retain the conservative guard</h3>
    <p>A more aggressive policy had a higher mean but four regressions above 5%; the retained guard had none in the same 96-pair pilot.</p>
  </div>

</div>

</div>

</div>

<div class="take am"><span class="lab">Safety claim</span>The placement is rejected if its channel-dependency graph is cyclic; adaptation cannot reverse dimension or leave the current DOR phase.</div>

<!--
Timing 35 s. The route table is static and cycle-aware. At runtime, unordered traffic can fall back to XY under pressure. Long packets require credit headroom. Safety comes from materializing every path and requiring an acyclic channel-dependency graph.
-->

---

# Bypass results

<p class="lede">Larger meshes amplify the benefit.</p>

<div class="body">

<div class="grid2">

<div class="stack">

  <table class="tbl">
    <thead><tr><th>Mesh</th><th class="r">Speedup</th><th class="r">Median</th><th class="r">Throughput</th><th class="r">Router/flit</th><th class="r">&gt;5% slow</th></tr></thead>
    <tbody>
      <tr><td>4×4</td><td class="num">1.291×</td><td class="num">1.068×</td><td class="num">+4.37%</td><td class="num">−17.37%</td><td class="num amb">1</td></tr>
      <tr><td>8×8</td><td class="num">1.583×</td><td class="num">1.132×</td><td class="num">+39.37%</td><td class="num">−18.84%</td><td class="num good">0</td></tr>
    </tbody>
  </table>

  <div class="cap" style="text-align:left">Each row has 768 matched pairs. Worst latency ratios: 0.909× on 4×4 and 0.954× on 8×8; 117 and 126 individual ratios are below one.</div>

  <div class="card am">
    <span class="mark">WHY 8×8 IMPROVES MORE</span>
    <h3>Longer paths, same guard</h3>
    <p>Repeated stride hops relieve loaded Router stages on longer routes, while conservative admission limits the negative tail.</p>
  </div>

</div>

<div class="stack">

  <table class="tbl">
    <thead><tr><th>Added resource</th><th class="r">4×4</th><th class="r">8×8</th></tr></thead>
    <tbody>
      <tr><td>Undirected express links</td><td class="num">16</td><td class="num">96</td></tr>
      <tr><td>Wire-span sum</td><td class="num">32</td><td class="num">192</td></tr>
      <tr><td>Max network degree</td><td class="num">6</td><td class="num">8</td></tr>
      <tr><td>Buffer-slot proxy</td><td class="num">768</td><td class="num">4,608</td></tr>
    </tbody>
  </table>

  <div class="card">
    <span class="mark">COMPARISON TYPE</span>
    <h3>Workload-matched, added-resource</h3>
    <p>Physical area and power remain outside Garnet; these proxies make the extra topology explicit.</p>
  </div>

</div>

</div>

</div>

<div class="take am"><span class="lab">Honest boundary</span>The gain is not iso-area, iso-power, or iso-wire. It says what the added links buy under matched traffic, not that the design is physically free.</div>

<!--
Timing 45 s. On 4x4, geometric-mean latency speedup is 1.291x and mean throughput improves 4.37 percent. On 8x8, those values are 1.583x and 39.37 percent. Router traversals fall by about 18 percent. The table also reports the added links, wire span, degree, and buffer proxies.
-->

---

# Tensor all-reduce

<p class="lede">Preserve all-reduce as tensor events.</p>

<div class="body">

<div class="grid2">

<div>

  <div class="fig" style="height:335px"><img src="/tensor_allreduce_pipeline.png" alt="Pipeline from traced all-reduce events through scalar and tensor lowerings to router reduction" /></div>
  <div class="cap">The manipulated variable is request representation; lane arithmetic, routes, release schedule, and counted network work stay fixed.</div>

</div>

<div class="stack">

  <div class="card vi">
    <span class="mark">TRACE SOURCE</span>
    <h3>8× H100 NCCL microbenchmark</h3>
    <p>PyTorch 2.8.0+cu128, CUDA 12.8, NCCL 2.27.3. The compiler keeps 15 broadcasts and 15 all-reduces: five repetitions each at 1, 4, and 16 MiB.</p>
  </div>

  <div class="card vi">
    <span class="mark">REPLAY SCALE</span>
    <h3>16-byte flits, 1/1024 scaling</h3>
    <p>Payload bytes and relative release times are scaled to a tractable Garnet replay. Results are simulation ticks, not native H100 timings.</p>
  </div>

  <div class="card vi">
    <span class="mark">TENSOR PATH</span>
    <h3>Lane-wise accumulation</h3>
    <p>Each flit carries a collective and lane ID. Routers accumulate the key, then forward or broadcast completed lanes; full outputs wait under backpressure.</p>
  </div>

</div>

</div>

</div>

<div class="take vi"><span class="lab">Controlled comparison</span>Scalar lowering repeats one-flit rounds; tensor lowering creates one multi-flit request per event and rank.</div>

<!--
Timing 35 s. Topic 4 uses a measured eight-H100 NCCL trace. After scaling, scalar lowering serializes lanes into independent rounds, while tensor lowering keeps one multi-flit request per event. Routers accumulate by collective and lane ID and preserve backpressure.
-->

---

# Replay results

<p class="lede">A scheduling win, not fewer bytes.</p>

<div class="body">

<div class="metrics">
  <div class="metric vi">
    <span class="v">4.728×</span>
    <span class="k">shorter replay window</span>
    <span class="n">80,638,000 → 17,054,500 ticks</span>
  </div>
  <div class="metric vi">
    <span class="v">53,760</span>
    <span class="k">source flits in both arms</span>
    <span class="n">same rank-lane deliveries</span>
  </div>
  <div class="metric vi">
    <span class="v">147,840</span>
    <span class="k">Router-forwarded flits</span>
    <span class="n">identical in both representations</span>
  </div>
</div>

<table class="tbl">
  <thead><tr><th>Replay view</th><th class="r">Trace events</th><th class="r">Logical requests</th><th class="r">Source flits</th><th class="r">Window</th></tr></thead>
  <tbody>
    <tr><td>Broadcast</td><td class="num">15</td><td class="num">30</td><td class="num">6,720</td><td class="num">17,047,500</td></tr>
    <tr><td>Scalar all-reduce</td><td class="num">15</td><td class="num">6,720</td><td class="num">53,760</td><td class="num">80,638,000</td></tr>
    <tr class="pick"><td>Tensor all-reduce</td><td class="num">15</td><td class="num">15</td><td class="num">53,760</td><td class="num">17,054,500</td></tr>
  </tbody>
</table>

</div>

<div class="take vi"><span class="lab">Boundary</span>The win comes from replacing 6,720 independently admitted scalar rounds with 15 event-level requests. Mesh XY and the bypass arm are identical here because selected routes follow ordinary XY and express flits are zero.</div>

<!--
Timing 40 s. Tensor replay reduces the window from 80.638 million to 17.0545 million ticks, 4.728 times. Source and Router-forwarded flit counts are identical, so this is a request-representation and scheduling result, not an H100 hardware speedup.
-->

---

# Conclusion

<p class="lede">Three claims, kept separate.</p>

<div class="body">

<div class="cards3">
  <div class="card cy">
    <span class="mark">TREE MULTICAST</span>
    <h3>Sharing is structural</h3>
    <p>Common-fanout traffic falls 39.51% on 4×4 and 34.95% on 8×8; scale-out reaches 75.39% at fanout 64. Atomic fanout explains the ten 4×4 regressions.</p>
  </div>
  <div class="card am">
    <span class="mark">PRESSURE-AWARE BYPASS</span>
    <h3>Useful, not free</h3>
    <p>Distance-scaled stride links give 1.291× and 1.583× mean latency speedup, with explicit added links, ports, wire span, and buffer proxies.</p>
  </div>
  <div class="card vi">
    <span class="mark">TENSOR ALL-REDUCE</span>
    <h3>Representation matters</h3>
    <p>Event-level requests finish the scaled trace 4.728× sooner while injecting and forwarding exactly the same flit counts.</p>
  </div>
</div>

</div>

<div class="take"><span class="lab">Design principle</span>Expose collective structure only where it removes demonstrable network work or request serialization; keep every claim beside its matched baseline and its resource boundary.</div>

<!--
Timing 25 s. Multicast removes duplicated link work, especially at high fanout. Bypass improves latency with added hardware and conservative admission. Tensor streaming preserves event structure and removes scalar serialization.
-->

---

# Division of labor

<p class="lede">Built separately, integrated together.</p>

<div class="body">

<div class="people">
  <div class="person">
    <div class="badge">CL</div>
    <div>
      <h3>Chunyu Liu</h3>
      <ul>
        <li>Garnet collective plumbing and tree multicast</li>
        <li>Express-link bypass design and evaluation</li>
        <li>H100 trace capture and compilation</li>
        <li>Aggregate analysis, figures, and report integration</li>
      </ul>
    </div>
  </div>
  <div class="person vi">
    <div class="badge">BP</div>
    <div>
      <h3>Boyan Pu</h3>
      <ul>
        <li>Tensor all-reduce implementation</li>
        <li>Replay tooling</li>
        <li>Backpressure and correctness validation</li>
        <li>Tensor experiments, statistics, and slide production</li>
      </ul>
    </div>
  </div>
</div>

</div>

<!--
Timing 15 s. Chunyu built the multicast and bypass mechanisms and the trace capture. Boyan built the tensor datapath, replay tooling, and validation. Integration and final reporting were done together.
-->

---
class: end-slide
---

# Thank you

<p class="lines">Multicast shares the tree.<br>Bypass pays for distance, then checks pressure.<br>Tensor replay preserves the event.</p>

<div class="row">
  <span><b>−75.39%</b>fanout-64 link flits</span>
  <span><b>1.583×</b>8×8 bypass latency</span>
  <span><b>4.728×</b>tensor replay window</span>
</div>

<!--
Timing 5 s. Thank you. I can return to the backup slides for exact comparisons and limitations.
-->

---

# Comparisons

<p class="lede">What exactly was compared?</p>

<div class="body">

<table class="tbl">
  <thead><tr><th>Study</th><th>New mechanism</th><th>Matched baseline</th><th>Primary evidence</th></tr></thead>
  <tbody>
    <tr><td>Tree multicast</td><td>One bitmap packet, replicated at pruned-tree branches</td><td>Replicated unicast on the same Mesh</td><td>Internal-link flits, latency, logical throughput</td></tr>
    <tr><td>Express bypass</td><td>Stride-2 links, multi-hop DOR table, runtime admission</td><td>Plain Mesh XY with fewer resources</td><td>Latency, throughput, traversals, cost proxies</td></tr>
    <tr><td>Tensor replay</td><td>15 event-level multi-flit requests</td><td>6,720 scalar-lane rounds</td><td>Replay window and identical flit counts</td></tr>
  </tbody>
</table>

<div class="formulas">
  <span>S_L = L_base / L_new</span>
  <span>R_F = 1 − F_new / F_base</span>
  <span>I_Q = Q_new / Q_base − 1</span>
</div>

</div>

<!--
Backup. This table records the exact paired comparison behind each headline number.
-->

---

# Scope and reproducibility

<p class="lede">Claims, limits, and revision provenance.</p>

<div class="body">

<div class="bounds">
  <div><b>Resource boundary</b><span>Bypass is workload-matched and added-resource, not iso-area, iso-power, or iso-wire; physical area and power are outside Garnet.</span></div>
  <div><b>Topology separation</b><span>Multicast common-fanout and 8×8 scale-out groups stay separate; fanout 32 and 64 are never pooled into the cross-topology mean.</span></div>
  <div><b>Trace scaling</b><span>H100 payload and release times are scaled by 1/1024; the reported window is Garnet simulation ticks, not native NVLink time.</span></div>
  <div><b>Neutral topology arm</b><span>The tensor trace's selected routes use ordinary XY, so Mesh XY and the bypass arm produce identical replay results.</span></div>
  <div><b>Revisions</b><span>Multicast/tensor: 77fcf26d57. Bypass evaluation: 1e8764cde7; pressure-aware source hash: ea4c3c9b0f.</span></div>
</div>

</div>

<div class="take"><span class="lab">Rebuild</span><code>plot_multicast.py</code> and <code>generate_architecture_figures.py</code> rebuild figures; <code>run_lab4_full_gate.py</code> runs the functional, backpressure, and trace suites.</div>

<!--
Backup. Use this slide for questions about resource fairness, scale-out pooling, trace scaling, or revisions.
-->
