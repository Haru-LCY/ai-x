# Multicast results

<p class="lede">Each Mesh aggregate covers its complete evaluated fanout range.</p>

<div class="body">

<div class="stack" style="max-width:900px;margin:30px auto 0">

  <table class="tbl multicast-summary">
    <thead><tr><th>Mesh</th><th>Fanouts</th><th class="r">Latency</th><th class="r">Link-flit red.</th><th class="r">Throughput</th></tr></thead>
    <tbody>
      <tr><td>4×4</td><td>4, 8, 16</td><td class="num">3.638×</td><td class="num">39.51%</td><td class="num">+190.89%</td></tr>
      <tr><td>8×8</td><td>4, 8, 16, 32, 64</td><td class="num">6.331×</td><td class="num">48.53%</td><td class="num">+681.77%</td></tr>
    </tbody>
  </table>

  <div class="cap" style="text-align:left">4×4 contains 162 matched cases; 8×8 contains 270. Latency is geometric mean; link-flit reduction and throughput are arithmetic means over all cases in each row.</div>

</div>

</div>

<div class="take cy"><span class="lab">Reading</span>Link-flit saving is structural. Latency includes the dedicated Router datapath. Throughput reflects the cost of coordinated fanout.</div>

<!--
这一页报告 multicast 的总体结果。我们在 4×4 和 8×8 两种 mesh 上测试了 fanout 4、8、16，
表格单独列出每个 Mesh 实际统计的 fanout。4×4 包含 fanout 4、8、16，共 162 个 matched cases；8×8 还包含 fanout 32 和 64，共 270 个 matched cases。Latency 使用 geometric mean，link-flit reduction 和 throughput change 使用 arithmetic mean。

4×4 平均减少 39.51% 的 link flits，latency 是 3.638× speedup，throughput 提升 190.89%。8×8 在完整 fanout 范围内平均减少 48.53% 的 link flits，latency 是 6.331×，throughput 提升 681.77%。
-->
