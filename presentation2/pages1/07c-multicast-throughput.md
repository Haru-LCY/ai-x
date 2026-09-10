# Throughput across fanout and packet size

<p class="lede">The throughput gain follows the same fanout-driven scaling trend.</p>

<div class="body">

  <div class="fig" style="height:445px"><img src="/throughput_change_by_group_packet.png" alt="Multicast logical-throughput change by topology, fanout, and packet size" /></div>
  <div class="cap">Bars are arithmetic means across matched load, background-load, and seed cases; whiskers show the observed min–max.</div>

</div>

<div class="take cy"><span class="lab">Reading</span>Higher fanout removes more source-generated copies; within a fanout, shorter packets show the largest mean throughput change.</div>

<!--
这张图用和 latency figure 相同的组织方式展示 logical throughput change：左右分别是 4×4 和 8×8，横轴是 fanout，颜色区分 1、4、16-flit packet。柱子是相同 load、background load 和 seed 下 paired comparison 的 arithmetic mean，whisker 是 observed range。两种 topology 上，throughput 的平均提升都会随 fanout 增大；在同一个 fanout 内，短 packet 通常提升最大。8×8 的 fanout 32 和 64 延续了相同趋势。
-->
