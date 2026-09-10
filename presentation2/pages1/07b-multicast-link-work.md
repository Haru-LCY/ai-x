# Internal-link flit reduction

<p class="lede">Shared route prefixes remove a larger fraction of link work as fanout grows.</p>

<div class="body">

  <div class="fig" style="height:445px"><img src="/internal_link_flit_reduction_by_group_packet.png" alt="Internal-link flit reduction by topology, fanout, and packet size" /></div>
  <div class="cap">Bars average matched offered-load, background-load, and seed cases; whiskers show the observed min–max.</div>

</div>

<div class="take cy"><span class="lab">Reading</span>Reduction rises with fanout on both Mesh sizes and reaches 75.39% at fanout 64.</div>

<!--
这张图把 internal-link flit reduction 按 topology、fanout 和 packet size 展开。左右分别是 4×4 和 8×8，横轴是 fanout，颜色区分 1、4、16-flit packet；柱子是 matched load、background load 和 seed 的 arithmetic mean，whisker 是 observed range。两种 Mesh 上 reduction 都随 fanout 增大，8×8 scale-out 在 fanout 32 达到 62.41%，fanout 64 达到 75.39%。
-->
