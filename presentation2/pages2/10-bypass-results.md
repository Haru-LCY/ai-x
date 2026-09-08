# Bypass results

<p class="lede">Across 1,536 matched runs per family, stride-2 scales best on 8×8.</p>

<div class="body">

<div class="sweep-note">
  We run 2 mesh sizes × 4 traffic patterns × 4 packet sizes × 16 offered loads × 3 seeds — <b>1,536 matched cases per bypass family</b>. Each case runs plain Mesh XY and one bypass arm with the same traffic, packet size, load, seed, and pre-generated source/destination counts, giving 3,072 gem5 runs per family.
</div>

<div class="sweep-grid">

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
    Distance-scaled diagonal and stride-2 · geometric-mean latency · arithmetic-mean throughput.
  </div>
</div>

<div>
  <div class="fig pattern-map"><img src="/bypass_traffic_pattern_structure.png" alt="Spatial source-to-destination structure of the uniform random, transpose, bit-complement, and hotspot traffic patterns" /></div>
  <div class="cap">Uniform random · transpose · bit-complement · hotspot · arrow: source → destination, node size: incoming traffic.</div>
</div>

</div>

<div class="metrics">
  <div class="metric am">
    <span class="v">1.620×</span>
    <span class="k">stride-2 latency on 8×8</span>
    <span class="n">the strongest topology/mesh aggregate</span>
  </div>
  <div class="metric">
    <span class="v">1.426×</span>
    <span class="k">diagonal latency on 4×4</span>
    <span class="n">the best diagonal aggregate</span>
  </div>
</div>

</div>

<div class="take am"><span class="lab">Honest boundary</span>These are workload-matched, added-resource comparisons: the extra links, ports, and buffers are not physically free.</div>

<!--
我们对于每个 bypass family 都做一个 matched-pair sweep：2 个 mesh size、4 种 traffic pattern、4 种 packet size、16 个 offered load、3 个 seed，相乘是 1,536 个 case；每个 case 分别跑一次 plain Mesh XY 和一次 bypass。运行前有 1,000 warm-up 和 5,000 measurement source cycles，之后 drain 和 cooldown；stride-2 在 8×8 最好：latency geometric mean 1.620×，throughput 平均 +39.37%。diagonal 在 4×4 也有 1.426×，但到 8×8 降到 1.165×，说明 placement 和 mesh size 的匹配很重要。
-->
