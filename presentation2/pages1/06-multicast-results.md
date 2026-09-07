# Multicast results

<p class="lede">Common-fanout gains, with regressions retained.</p>

<div class="body">

<div class="grid2">

<div>

  <div class="fig" style="height:275px"><img src="/traffic_reduction_by_group.png" alt="Internal-link flit reduction by topology and destination count" /></div>
  <div class="cap">4×4 and 8×8 common-fanout results are reported separately; fanout 32 and 64 are scale-out only.</div>

</div>

<div class="stack">

  <table class="tbl">
    <thead><tr><th>Mesh</th><th class="r">Link-flit red.</th><th class="r">Latency</th><th class="r">Throughput</th><th class="r">Regress.</th></tr></thead>
    <tbody>
      <tr><td>4×4 · 162 pairs</td><td class="num">39.51%</td><td class="num">3.638×</td><td class="num">+190.89%</td><td class="num bad">10</td></tr>
      <tr><td>8×8 · 162 pairs</td><td class="num">34.95%</td><td class="num">3.472×</td><td class="num">+208.34%</td><td class="num good">0</td></tr>
    </tbody>
  </table>

  <div class="cap" style="text-align:left">Latency is geometric mean; link-flit reduction and throughput are arithmetic means. Medians: 41.18%/29.63% traffic and 3.588×/2.667× latency.</div>

  <div class="card cy">
    <span class="mark">WHY THE 4×4 CASES SLOW</span>
    <h3>Atomic branch coupling</h3>
    <p>All ten regressions are fanout-4 cases; the worst is <b>−18.24%</b>. A congested output can hold the reservation while other branches wait.</p>
  </div>

</div>

</div>

</div>

<div class="take cy"><span class="lab">Reading</span>Link-flit saving is structural. Latency includes the dedicated Router datapath. Throughput exposes synchronization cost rather than being folded into a single score.</div>

<!--
Timing 45 s. At common fanouts, 4x4 removes 39.51 percent of internal-link flits and 8x8 removes 34.95 percent. Latency speedups are 3.638x and 3.472x. Mean throughput improves in both studies, but 4x4 has ten fanout-four regressions caused by atomic branch coupling; 8x8 has none.
-->
