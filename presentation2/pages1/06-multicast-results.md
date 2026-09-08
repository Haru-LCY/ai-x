# Multicast results

<p class="lede">Common-fanout gains across Mesh sizes.</p>

<div class="body">

<div class="grid2">

<div>

  <div class="fig" style="height:275px"><img src="/traffic_reduction_common.png" alt="Internal-link flit reduction by topology and common fanout" /></div>
  <div class="cap">Each bar averages the 1-, 4-, and 16-flit packet cases at that common fanout; error bars show the observed min–max.</div>

</div>

<div class="stack">

  <table class="tbl multicast-summary">
    <thead><tr><th>Metric</th><th class="r">4×4</th><th class="r">8×8</th></tr></thead>
    <tbody>
      <tr><td>Link-flit red.</td><td class="num">39.51%</td><td class="num">34.95%</td></tr>
      <tr><td>Latency</td><td class="num">3.638×</td><td class="num">3.472×</td></tr>
      <tr><td>Throughput</td><td class="num">+190.89%</td><td class="num">+208.34%</td></tr>
    </tbody>
  </table>

  <div class="cap" style="text-align:left">Latency is geometric mean; link-flit reduction and throughput are arithmetic means. Medians: 41.18%/29.63% traffic and 3.588×/2.667× latency.</div>

</div>

</div>

</div>

<div class="take cy"><span class="lab">Reading</span>Link-flit saving is structural. Latency includes the dedicated Router datapath. Throughput reflects the cost of coordinated fanout.</div>

<!--
这一页报告 multicast 的总体结果。我们在 4×4 和 8×8 两种 mesh 上测试了 fanout 4、8、16，
表格和 figure 中的数值都平均了 1、4、16-flit packet case，表格汇总了对于不同fanout的 latency 和 throughput。

先看 4×4。平均减少 39.51% 的 link flits，latency 是 3.638× speedup，throughput 提升 190.89%。8×8 也减少 34.95% 的 link flits，latency 是 3.472×，throughput 提升 208.34%。这里 latency 使用 geometric mean，link-flit reduction 和 throughput 使用 arithmetic mean。
-->
