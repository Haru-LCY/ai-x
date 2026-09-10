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
    <h3>Offline multi-hop routes</h3>
    <p>Stride keeps X-before-Y DOR; diagonal uses an X* → diagonal* → Y* static chain. Every express entry must lower the complete remaining path cost.</p>
  </div>
  <div class="card">
    <span class="mark">BASELINE</span>
    <h3>Plain Mesh XY</h3>
    <p>The comparator has fewer links, ports, VCs, and buffers. This is an added-resource comparison, not iso-area or iso-power.</p>
  </div>
</div>

</div>

<!--
第二部分是 express-link bypass。我们保留普通 Mesh，增加 diagonal 和 stride-2 两种 placement。Stride 的静态路径保持 X-before-Y DOR，diagonal 的静态路径是 X、diagonal、Y 三阶段；只有能降低完整剩余路径 cycle cost 的 express edge 才会进入表。Baseline 是 plain Mesh XY；bypass arm 额外增加 links、ports 和 buffers，因此这里比较的是增加这些资源后的性能。
-->
