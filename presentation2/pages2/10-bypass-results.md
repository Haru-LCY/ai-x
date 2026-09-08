# Bypass results

<p class="lede">With distance-scaled wires, stride-2 scales better on 8×8.</p>

<div class="body">

<div>
  <table class="tbl result-summary">
    <thead><tr><th>Topology</th><th>Mesh</th><th class="r">Latency</th><th class="r">Throughput</th></tr></thead>
    <tbody>
      <tr><td>Diagonal</td><td>4×4</td><td class="num">1.426×</td><td class="num">+4.27%</td></tr>
      <tr><td>Diagonal</td><td>8×8</td><td class="num">1.165×</td><td class="num">+12.90%</td></tr>
      <tr><td>Stride-2</td><td>4×4</td><td class="num">1.312×</td><td class="num">+4.37%</td></tr>
      <tr class="pick"><td>Stride-2</td><td>8×8</td><td class="num">1.620×</td><td class="num">+39.37%</td></tr>
    </tbody>
  </table>

  <div class="cap">
    Distance-scaled diagonal and stride-2 · geometric-mean latency · arithmetic-mean throughput · 1,536 matched pairs per bypass family.
  </div>
</div>

<div class="metrics">
  <div class="metric am">
    <span class="v">1.620×</span>
    <span class="k">stride-2 latency on 8×8</span>
    <span class="n">the strongest topology/mesh aggregate</span>
  </div>
  <div class="metric">
    <span class="v">1.165×</span>
    <span class="k">diagonal latency on 8×8</span>
    <span class="n">the same placement does not continue scaling</span>
  </div>
</div>

</div>

<div class="take am"><span class="lab">Honest boundary</span>These are workload-matched, added-resource comparisons: the extra links, ports, and buffers are not physically free.</div>

<!--
Timing 25 s. 先看汇总。这里两个 bypass arm 都用 distance-scaled wires，没有 optimistic。stride-2 在 8×8 最好：latency geometric mean 1.620×，throughput 平均 +39.37%。diagonal 在 4×4 也有 1.426×，但到 8×8 降到 1.165×，说明 placement 和 mesh size 的匹配很重要。后面两页分别看 latency 和 throughput 的 traffic-pattern 细分。最后记住口径：这是 workload-matched、added-resource comparison。
-->
