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
