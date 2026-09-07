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
