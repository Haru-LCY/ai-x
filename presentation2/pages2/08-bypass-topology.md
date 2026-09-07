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
