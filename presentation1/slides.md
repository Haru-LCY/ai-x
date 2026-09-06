---
theme: default
title: Collective Communication for Mesh NoCs
info: |
  Lab 4 Topic 3 and Topic 4 presentation.
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

<div class="body">
<div>

<div class="kicker">Lab 4 · Topic 3 + Topic 4</div>

# Collective-aware<br><span class="accent">Mesh NoCs</span>

<p class="sub">Router-level tree multicast, physical express-link bypass,<br>and trace-driven tensor all-reduce in gem5 Garnet.</p>

<div class="who"><span>Chunyu Liu</span><i></i><span>Boyan Pu</span></div>

<div class="tags">
  <span>Multicast</span>
  <span>Bypass express links</span>
  <span>H100 trace replay</span>
</div>

</div>
<div>

<div class="mesh" aria-hidden="true">
  <i></i><i></i><i class="c"></i><i></i><i></i>
  <i></i><i></i><i class="c"></i><i></i><i></i>
  <i></i><i class="c"></i><i class="c"></i><i class="c"></i><i></i>
  <i></i><i class="a"></i><i></i><i class="c"></i><i></i>
  <i></i><i></i><i></i><i></i><i></i>
  <div class="mesh-legend"><span><i></i>XY route</span><span class="a"><i></i>Express link</span></div>
</div>

</div>
</div>

<!--
Hello. We study how a Mesh NoC can expose the structure of collective communication instead of lowering it into unrelated unicast traffic. Topic 3 is our main study: tree multicast and express-link bypass. We close with a Topic 4 trace case study. Timing: 20 seconds.
-->

---

<div class="kicker">Motivation</div>

# One synchronization barrier, three separable costs

<div class="body" style="grid-template-rows:auto auto;">

<div class="flow">
  <div class="step"><b>Compute</b><span>each rank produces a local gradient</span></div>
  <div class="sep">→</div>
  <div class="step hot"><b>Collective</b><span>the network is on the critical path</span></div>
  <div class="sep">→</div>
  <div class="step"><b>Continue</b><span>the next step consumes the result</span></div>
</div>

<div class="cards3">
  <div class="mech cyan">
    <span class="mark">1 → N</span>
    <h3>Replication</h3>
    <p>Independent unicasts retransmit the same route prefixes to every destination.</p>
    <span class="who">Tree multicast</span>
  </div>
  <div class="mech amber">
    <span class="mark">A ··· B</span>
    <h3>Path length</h3>
    <p>Distant pairs consume many intermediate Routers and links per packet.</p>
    <span class="who">Express-link bypass</span>
  </div>
  <div class="mech violet">
    <span class="mark">6,720 → 15</span>
    <h3>Representation</h3>
    <p>Scalarizing one tensor collective creates avoidable request serialization.</p>
    <span class="who">Tensor streaming</span>
  </div>
</div>

</div>

<div class="take"><span class="lab">Claim discipline</span>Fewer link flits, lower latency, and fewer logical requests are <b>three different claims</b> — each is measured against its own matched baseline.</div>

<!--
Training repeatedly stops at a communication barrier. We separate three costs: replication, path length, and representation. Keeping them separate matters, because a traffic reduction, a latency ratio and a request-count ratio are not the same result. Timing: 40 seconds.
-->

---

<div class="kicker">Architecture</div>

# Two collective datapaths over one Mesh XY network

<div class="body">
<div class="cols rev">

<div class="stack">

<div class="fact cyan">
  <b>Bitmap multicast</b>
  <span>One packet carries a 64-bit destination mask. Each Router delivers locally if selected and forwards only on branches that still have destinations.</span>
</div>

<div class="fact violet">
  <b>Convergence-tree all-reduce</b>
  <span>Each Router stores <code>parent_outport</code>, <code>child_inports</code> and <code>expected_fanin</code> derived from XY routes toward the root; results return along the reversed edges.</span>
</div>

<div class="fact">
  <b>Shared principle, distinct logic</b>
  <span>Both reuse tree paths, but multicast routes source→destinations while all-reduce routes node→root. They are separate implementations.</span>
</div>

</div>

<div>
  <div class="fig" style="height:372px"><img src="/multicast_tree_flow.png" alt="Replicated unicast versus tree multicast on a 4x4 Mesh" /></div>
  <div class="cap">Left: one packet per destination. Right: one bitmap packet replicated at branch Routers.</div>
</div>

</div>
</div>

<div class="take cyan"><span class="lab">Baseline network</span>Deterministic <b>Mesh XY</b> in Garnet; every comparison keeps topology, traffic, packet sequence and seed fixed.</div>

<!--
Our base network is deterministic Mesh XY. We built two collective datapaths on it. Bitmap multicast carries a destination mask and replicates at branch routers. The all-reduce path uses precomputed parent, children and fan-in metadata to converge values toward a root and broadcast back. They share the idea of reusing tree paths, but they are distinct routing logic. Timing: 40 seconds.
-->

---

<div class="kicker cyan">Topic 3 · Multicast — implementation</div>

# Replicate at branch Routers, not at the source

<div class="body" style="grid-template-rows:auto auto;">

<div class="vs">
  <div class="side">
    <div class="lbl">BASELINE · REPLICATED UNICAST</div>
    <div class="pkts"><span>dst A</span><span>dst B</span><span>dst C</span><span>dst D</span></div>
    <p>The Network Interface injects one physical packet per destination, so every shared prefix is transmitted repeatedly.</p>
  </div>
  <div class="mid">VS</div>
  <div class="side new">
    <div class="lbl">NEW · TREE MULTICAST</div>
    <div class="bitmap"><b>HEAD</b><span>64-bit destination mask</span></div>
    <p>One injected packet. Routers copy head, body and tail flits only onto branches that still lead to destinations.</p>
  </div>
</div>

<div class="steps4">
  <div><b>Route</b><span>compute required output branches from the mask</span></div>
  <div><b>Deliver</b><span>eject locally when this Router is selected</span></div>
  <div><b>Replicate</b><span>copy per branch, keeping multi-flit order</span></div>
  <div class="warn"><b>Atomic fanout</b><span>a flit advances only when every branch has credit</span></div>
</div>

</div>

<div class="take cyan"><span class="lab">Fair contract</span>Both arms use the <b>same logical request</b>, destination set, packet size, background traffic and completion condition — one complete packet must reach every destination.</div>

<!--
The baseline lowers one logical multicast into one packet per destination. Our path injects a single packet carrying a 64-bit destination mask. Routers deliver locally when selected and replicate only onto branches that still have destinations. To keep multi-flit delivery exact under backpressure, fanout is atomic: a flit advances only when all selected branches have credit. That coupling explains the regressions on the next slide. Timing: 50 seconds.
-->

---

<div class="kicker cyan">Topic 3 · Multicast — evaluation</div>

# Traffic saving is structural; throughput is workload dependent

<div class="body" style="grid-template-rows:auto 1fr;">

<div class="metrics">
  <div class="metric">
    <span class="v">−39.51%</span>
    <span class="k">mean internal-link flits</span>
    <span class="n">162 paired cases · median −41.18%</span>
  </div>
  <div class="metric">
    <span class="v">4.790×</span>
    <span class="k">mean latency speedup</span>
    <span class="n">implemented system, incl. Router fast path</span>
  </div>
  <div class="metric warn">
    <span class="v">10 / 162</span>
    <span class="k">throughput regressions</span>
    <span class="n">all at fanout 4 · worst −18.24%</span>
  </div>
</div>

<div class="cols">
  <div class="fig"><img src="/traffic_reduction_by_group.png" alt="Internal-link flit reduction by destination count" /></div>
  <div class="stack">
    <table class="tbl">
      <thead><tr><th>Destinations</th><th style="text-align:right">Link-flit saving</th><th style="text-align:right">Regressions</th></tr></thead>
      <tbody>
        <tr><td>4</td><td class="num">−26.19%</td><td class="num neg">10 / 54</td></tr>
        <tr><td>8</td><td class="num">−39.22%</td><td class="num">0 / 54</td></tr>
        <tr><td>16</td><td class="num">−53.13%</td><td class="num">0 / 54</td></tr>
      </tbody>
    </table>
    <div class="cap">The saving is monotone in fanout; every regression sits in the smallest, most loaded group.</div>
  </div>
</div>

</div>

<div class="take cyan"><span class="lab">Reading</span>Link flits are the <b>structural</b> claim. Latency is an <b>implemented-system</b> result, since collective flits use a dedicated Router fast path rather than the ordinary unicast allocator.</div>

<!--
Across 162 paired cases tree multicast removes 39.51 percent of internal-link flits, rising from 26.19 percent at four destinations to 53.13 percent at sixteen. Latency also improves, but we report that as an implemented-system result because collective flits use a dedicated router fast path. Ten cases regress in throughput, all at fanout four, which is consistent with atomic fanout coupling branches. Timing: 55 seconds.
-->

---

<div class="kicker amber">Topic 3 · Bypass — implementation</div>

# A shortcut is admitted only if it provably shortens and stays safe

<div class="body">
<div class="cols">

<div>
  <div class="fig" style="height:398px"><img src="/bypass_topology_oracle.png" alt="Diagonal and stride express-link placements with oracle-selected first hop" /></div>
  <div class="cap">Diagonal (9 links) and stride-2 (16 links) placements on 4×4, with the oracle-selected express first hop.</div>
</div>

<div class="stack">

<div class="steps">
  <div class="row"><em>1</em><div><b>Install express links</b><span>Bidirectional diagonal or stride links added to the ordinary Mesh.</span></div></div>
  <div class="row"><em>2</em><div><b>Enumerate all pairs offline</b><span>The oracle considers at most one express hop, taken at the source.</span></div></div>
  <div class="row"><em>3</em><div><b>Require strictly fewer hops</b><span>1 + dist(landing, dst) &lt; dist(src, dst); the suffix stays deterministic XY.</span></div></div>
  <div class="row"><em>4</em><div><b>Audit the dependency graph</b><span>Build the all-pairs channel-dependency graph; reject any cyclic placement.</span></div></div>
</div>

</div>
</div>
</div>

<div class="take amber"><span class="lab">Wire models</span><b>Optimistic</b> — every express link costs one cycle · <b>Distance-scaled</b> — link and credit latency scale with the Manhattan span (hardware-relevant). The oracle minimizes <b>hop count</b>, not modeled latency.</div>

<!--
Bypass installs real diagonal or stride links. An offline oracle enumerates every source-destination pair and keeps at most one source express hop, only when it strictly reduces the remaining hop count; the rest of the route is deterministic XY. We build the channel dependency graph over all pairs and reject cyclic placements, which gives the deadlock-safety argument. Note the oracle minimizes hops, not modeled latency. Timing: 50 seconds.
-->

---

<div class="kicker amber">Topic 3 · Bypass — evaluation</div>

# Saved hops do not automatically become saved time

<div class="body">
<div class="cols">

<div>
  <div class="fig" style="height:382px"><img src="/bypass_overall.png" alt="Latency speedup and throughput change for four bypass designs" /></div>
  <div class="cap">1,536 paired seed cases per design · 4 traffic patterns · 16 offered loads · 2 Mesh sizes.</div>
</div>

<div class="stack">

<table class="tbl">
  <thead><tr><th>Design</th><th style="text-align:right">Latency</th><th style="text-align:right">Slower cases</th></tr></thead>
  <tbody>
    <tr class="pick"><td>Diagonal · distance-scaled</td><td class="num amb">1.629×</td><td class="num amb">687 / 1536</td></tr>
    <tr><td>Diagonal · optimistic</td><td class="num">1.723×</td><td class="num">160 / 1536</td></tr>
    <tr><td>Stride · distance-scaled</td><td class="num neg">0.981×</td><td class="num neg">968 / 1536</td></tr>
    <tr><td>Stride · optimistic</td><td class="num">1.103×</td><td class="num">311 / 1536</td></tr>
  </tbody>
</table>

<div class="fact amber">
  <b>Physical cost on 4×4</b>
  <span>Diagonal: 9 links, wire proxy 18, max radix 8 · Stride: 16 links, wire proxy 32, max radix 6.</span>
</div>

</div>
</div>
</div>

<div class="take amber"><span class="lab">Honest reading</span>Diagonal wins the <b>mean</b>, yet still regresses in 687 of 1,536 cases — bypass is a <b>conditional</b> mechanism, not a general hop-count win.</div>

<!--
This is our primary bypass sweep. Distance-scaled diagonal links reach 1.629 times mean latency speedup, while distance-scaled stride links average 0.981 times despite removing more router traversals, because stride costs twice the wire budget. The important caveat is the third column: even the winning design is slower in 687 of 1,536 cases. The mean hides a wide distribution. Timing: 55 seconds.
-->

---

<div class="kicker">Topic 3 · Interaction</div>

# The two mechanisms target different bottlenecks

<div class="body" style="grid-template-rows:auto auto;">

<div class="duo">
  <div class="box cy">
    <div class="h">MULTICAST</div>
    <b>Removes duplicated work</b>
    <span>Shares route prefixes, so most redundant traversals are already gone before any shortcut exists.</span>
  </div>
  <div class="box am">
    <div class="h">BYPASS</div>
    <b>Shortens long routes</b>
    <span>Helps structured or distant unicast traffic — when the wire cost of the shortcut is justified.</span>
  </div>
</div>

<div class="stat3">
  <div><span class="v">416</span><span class="k">paired interaction cases (2×2, 3×3, 4×4)</span></div>
  <div><span class="v">0.965×</span><span class="k">replicated unicast + scaled bypass</span></div>
  <div><span class="v">0.988×</span><span class="k">tree multicast + scaled bypass</span></div>
</div>

</div>

<div class="take"><span class="lab">Design decision</span>Our policy <b>rejects a shortcut whose destination shares a route edge with another destination</b> — breaking a shared prefix costs more than the saved hop. Combining the mechanisms is neutral, not additive.</div>

<!--
The mechanisms are complementary but not additive. Across 416 interaction pairs, distance-scaled bypass averages 0.965 for replicated unicast and 0.988 for tree multicast — both slightly below one. So we made the multicast policy cost-aware: it rejects an express hop when that destination shares a route edge with another destination, because breaking the shared prefix costs more than the saved hop. Timing: 35 seconds.
-->

---

<div class="kicker violet">Topic 4 · Trace case study</div>

# Keep the tensor as one request, not 6,720 scalar lanes

<div class="body">
<div class="cols rev">

<div class="stack">

<div class="fact violet">
  <b>8× NVIDIA H100, executed</b>
  <span>NCCL collective microbenchmark (PyTorch 2.8 / CUDA 12.8 / NCCL 2.27.3). 15 measured all-reduce events; bytes and release times scaled by 1/1024.</span>
</div>

<div class="transform">
  <div class="b"><b>Scalar lowering</b><span>6,720 lanes</span></div>
  <div class="ar">→</div>
  <div class="b keep"><b>Tensor streaming</b><span>15 requests</span></div>
</div>

<table class="tbl">
  <thead><tr><th>Held constant</th><th style="text-align:right">Both lowerings</th></tr></thead>
  <tbody>
    <tr><td>Rank contributions</td><td class="num">53,760</td></tr>
    <tr><td>Router-generated flits</td><td class="num">147,840</td></tr>
    <tr><td>Express-link flits used</td><td class="num">0</td></tr>
  </tbody>
</table>

</div>

<div>
  <div class="fig" style="height:342px"><img src="/tensor_measurement_comparison.png" alt="Scalar versus tensor replay measurement window" /></div>
  <div class="cap">80,638,000 → 17,054,500 ticks: <b>4.728× shorter replay window</b> with identical traffic.</div>
</div>

</div>
</div>

<div class="take violet"><span class="lab">Boundary</span>A <b>representation</b> result in Garnet. The all-reduce tree uses ordinary Mesh edges, so both topology arms tie — a controlled neutral comparison, <b>not</b> an H100 or training speedup.</div>

<!--
For Topic 4 we replay an executed eight-H100 NCCL microbenchmark. The scalar lowering serializes fifteen tensors into 6,720 lanes; the tensor path keeps fifteen multi-flit requests and reduces them in the routers. Both move identical contributions and router flits, yet the tensor window is 4.728 times shorter. Note the all-reduce tree uses ordinary mesh edges, so bypass selects no express hop here — the topology comparison is deliberately neutral. Timing: 55 seconds.
-->

---

<div class="kicker">Conclusion</div>

# What the evidence supports

<div class="body">
<div class="concl">
  <div class="c cy">
    <span class="v">−39.51%</span>
    <h3>Expose shared structure</h3>
    <p>Tree multicast reliably removes duplicated link traffic, and the saving grows with fanout — but atomic fanout can stall a branch.</p>
  </div>
  <div class="c am">
    <span class="v">1.629×</span>
    <h3>Price every shortcut</h3>
    <p>Diagonal bypass wins on the mean under distance-scaled wires; stride's larger wire budget erases its hop advantage.</p>
  </div>
  <div class="c vi">
    <span class="v">4.728×</span>
    <h3>Preserve request semantics</h3>
    <p>Tensor streaming removes scalar serialization while injecting exactly the same contributions and Router flits.</p>
  </div>
</div>
</div>

<div class="take"><span class="lab">Design principle</span>Expose collective structure where it removes <b>demonstrable</b> network work; admit shortcuts only with <b>cost and safety checks</b>; report every mechanism against a <b>matched baseline</b> — negative cases included.</div>

<!--
Our three conclusions are deliberately separate. Multicast removes duplicated link work. Diagonal bypass helps on average once wire cost is modeled, but it is conditional. Tensor streaming reduces serialization without reducing traffic. The common rule: expose collective structure only where a matched baseline demonstrates the benefit. Timing: 35 seconds.
-->

---

<div class="kicker">Division of labor</div>

# Built separately, integrated and verified together

<div class="body">
<div class="people">
  <div class="person">
    <div class="badge">CL</div>
    <h3>Chunyu Liu</h3>
    <ul>
      <li>Tree multicast datapath and replicated-unicast baseline</li>
      <li>Bypass topologies, routing oracle and cost-aware policy</li>
      <li>Correctness matrices and the paired performance sweeps</li>
      <li>H100 collective trace capture and broadcast replay</li>
    </ul>
  </div>
  <div class="person vi">
    <div class="badge">BP</div>
    <h3>Boyan Pu</h3>
    <ul>
      <li>Multi-flit tensor all-reduce datapath</li>
      <li>Replay contract, compiler and validator</li>
      <li>Backpressure and credit-conservation stress tests</li>
      <li>Tensor statistics and the paired replay comparison</li>
    </ul>
  </div>
</div>
</div>

<div class="take"><span class="lab">Shared</span>Branch integration · regression review · final quantitative snapshot · report and figure verification.</div>

<!--
We divided the work by mechanism. Chunyu implemented multicast, bypass and trace capture. Boyan implemented the tensor all-reduce datapath, its contract, validators and stress tests. We jointly integrated branches, reviewed regressions, reran the final snapshot and verified the report. Timing: 25 seconds.
-->

---
class: end-slide
---

<div class="kicker">gem5 Garnet · Topic 3 + Topic 4</div>

# Thank you

<p class="lines">Multicast shares duplicated work.<br>Bypass has to pay for distance.<br>Tensor streaming preserves the request.</p>

<div class="row">
  <span><b>39.51%</b> fewer link flits</span>
  <span><b>1.629×</b> diagonal bypass</span>
  <span><b>4.728×</b> replay window</span>
</div>

<!--
Thank you — we are happy to take questions. Timing: 10 seconds. Total: about 7 minutes 45 seconds.
-->

---

<div class="kicker">Backup · evaluation contract</div>

# What exactly was compared?

<div class="body">

<table class="tbl">
  <thead><tr><th>Study</th><th>New mechanism</th><th>Matched baseline</th><th>Primary evidence</th></tr></thead>
  <tbody>
    <tr><td>Multicast</td><td>One bitmap packet, replicated at branch Routers</td><td>4/8/16 independent packets, identical Mesh</td><td>Internal-link flits</td></tr>
    <tr><td>Bypass</td><td>Express links + static routing oracle</td><td>Same Mesh with no express links</td><td>Latency, throughput, wire cost</td></tr>
    <tr><td>Tensor replay</td><td>15 multi-flit logical requests</td><td>6,720 serialized scalar lanes</td><td>End-to-end replay window</td></tr>
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

<div class="kicker">Backup · interpretation boundary</div>

# Where these results stop

<div class="body">

<div class="bounds">
  <div><b>Multicast</b><span>One 4×4 source placement (Router 5); collective flits use a dedicated Router fast path, so latency is not an isolated replication effect.</span></div>
  <div><b>Bypass</b><span>Wire cost is a latency and static-cost proxy — no area, power, repeaters or timing closure. The oracle minimizes hops, not modeled latency.</span></div>
  <div><b>Trace</b><span>An executed collective microbenchmark, not a full model trace; bytes and times are scaled by 1/1024, and rank values are deterministic test values.</span></div>
  <div><b>Tensor</b><span>No finite accumulator capacity and no modeled arithmetic pipeline latency.</span></div>
  <div><b>Overall</b><span>Cycle-level Garnet mechanism results — not NVLink/NVSwitch hardware or end-to-end training throughput.</span></div>
</div>

</div>
