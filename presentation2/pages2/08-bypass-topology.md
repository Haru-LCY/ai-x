# Bypass topology

<!-- <p class="lede">Stride-2 links priced by wire span.</p> -->

<div class="body" style="grid-template-rows:auto 1fr;gap:14px">

<div class="grid2">

<div>

  <div class="fig" style="height:270px"><img src="/bypass_diagonal_4x4.png" alt="Phase-ordered diagonal bypass alternative on a 4 by 4 mesh" /></div>
  <div class="cap">Diagonal</div>

</div>

<div>

  <div class="fig" style="height:270px"><img src="/bypass_stride_4x4.png" alt="Proposed stride-2 bypass topology on a 4 by 4 mesh" /></div>
  <div class="cap">Stride-2 hops while preserving DOR</div>

</div>

</div>

<div class="cards3">
  <div class="card am">
    <span class="mark">MESH BYPASS</span>
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
Timing 35 s. 第二个机制是 express-link bypass。我们保留普通 Mesh，再加入双向 stride-2 links，让 packet 可以跳过中间 Router。左边的 diagonal placement 是备选方案，右边的 repeated stride-2 hops 才是主设计。Route table 仍然遵守先 X 后 Y 的 DOR 顺序，而且只有当考虑 wire span 后，express edge 确实降低剩余路径成本时才会选它。Baseline 是更少资源的 plain Mesh XY，所以这是 added-resource comparison。
-->
