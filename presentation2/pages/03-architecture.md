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
