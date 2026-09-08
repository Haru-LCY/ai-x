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
第二部分是 express-link bypass。我们保留普通 Mesh，增加了两种 bypass 架构。第一种 diagonal placement，第二种是 stride-2 placement。flit 可以通过这些快速通道来跳过一些 router 节点。但是要说明的一点就是这个实现是没有考虑实际硬件资源的实现，比如这个 stride 2 就是把规则允许的 shortcuts 都放进去，Baseline 就是 plain Mesh XY
-->
