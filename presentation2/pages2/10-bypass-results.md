# Bypass results

<p class="lede">Across 1,536 matched cases per family, stride-2 scales best on 8×8.</p>

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
    Latency: geomean over load × seed per packet size, arithmetic mean over packet sizes, then geomean over traffic patterns. Throughput: arithmetic mean over all matched cases.
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

<div class="take am"><span class="lab">Comparison scope</span>These are workload-matched, added-resource comparisons: the bypass arms add links, ports, and buffers to plain Mesh XY.</div>

<!--
我们对于每个 bypass family 都做一个 matched-pair sweep：2 个 mesh size、4 种 traffic pattern、4 种 packet size、16 个 offered load、3 个 seed，相乘是 1,536 个 case；每个 case 分别跑一次 plain Mesh XY 和一次 bypass。运行前有 1,000 warm-up 和 5,000 measurement source cycles，之后 drain 和 cooldown。Latency 的汇总顺序是：先在每个 packet size 内对 load 和 seed 做 geometric mean，再对四个 packet size 做 arithmetic mean，最后对四种 traffic pattern 做 geometric mean；throughput 对全部 matched cases 做 arithmetic mean。按这个与图表一致的口径，stride-2 在 8×8 是 1.620× 和 +39.37%，diagonal 在 4×4 是 1.426×，到 8×8 是 1.165×。
-->
