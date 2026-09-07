# Bypass results

<p class="lede">Larger meshes amplify the benefit.</p>

<div class="body">

<div class="grid2">

<div class="stack">

  <table class="tbl">
    <thead><tr><th>Mesh</th><th class="r">Speedup</th><th class="r">Median</th><th class="r">Throughput</th><th class="r">Router/flit</th><th class="r">&gt;5% slow</th></tr></thead>
    <tbody>
      <tr><td>4×4</td><td class="num">1.291×</td><td class="num">1.068×</td><td class="num">+4.37%</td><td class="num">−17.37%</td><td class="num amb">1</td></tr>
      <tr><td>8×8</td><td class="num">1.583×</td><td class="num">1.132×</td><td class="num">+39.37%</td><td class="num">−18.84%</td><td class="num good">0</td></tr>
    </tbody>
  </table>

  <div class="cap" style="text-align:left">Each row has 768 matched pairs. Worst latency ratios: 0.909× on 4×4 and 0.954× on 8×8; 117 and 126 individual ratios are below one.</div>

  <div class="card am">
    <span class="mark">WHY 8×8 IMPROVES MORE</span>
    <h3>Longer paths, same guard</h3>
    <p>Repeated stride hops relieve loaded Router stages on longer routes, while conservative admission limits the negative tail.</p>
  </div>

</div>

<div class="stack">

  <table class="tbl">
    <thead><tr><th>Added resource</th><th class="r">4×4</th><th class="r">8×8</th></tr></thead>
    <tbody>
      <tr><td>Undirected express links</td><td class="num">16</td><td class="num">96</td></tr>
      <tr><td>Wire-span sum</td><td class="num">32</td><td class="num">192</td></tr>
      <tr><td>Max network degree</td><td class="num">6</td><td class="num">8</td></tr>
      <tr><td>Buffer-slot proxy</td><td class="num">768</td><td class="num">4,608</td></tr>
    </tbody>
  </table>

  <div class="card">
    <span class="mark">COMPARISON TYPE</span>
    <h3>Workload-matched, added-resource</h3>
    <p>Physical area and power remain outside Garnet; these proxies make the extra topology explicit.</p>
  </div>

</div>

</div>

</div>

<div class="take am"><span class="lab">Honest boundary</span>The gain is not iso-area, iso-power, or iso-wire. It says what the added links buy under matched traffic, not that the design is physically free.</div>

<!--
Timing 45 s. On 4x4, geometric-mean latency speedup is 1.291x and mean throughput improves 4.37 percent. On 8x8, those values are 1.583x and 39.37 percent. Router traversals fall by about 18 percent. The table also reports the added links, wire span, degree, and buffer proxies.
-->
