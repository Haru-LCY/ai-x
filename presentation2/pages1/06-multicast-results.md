# Multicast results

<p class="lede">Common-fanout gains, with slower cases retained.</p>

<div class="body">

<div class="grid2">

<div>

  <div class="fig" style="height:275px"><img src="/traffic_reduction_by_group.png" alt="Internal-link flit reduction by topology and destination count" /></div>
  <div class="cap">4×4 and 8×8 common-fanout results are reported separately; fanout 32 and 64 are scale-out only.</div>

</div>

<div class="stack">

  <table class="tbl">
    <thead><tr><th>Mesh</th><th class="r">Link-flit red.</th><th class="r">Latency</th><th class="r">Throughput</th><th class="r">Slower than unicast</th></tr></thead>
    <tbody>
      <tr><td>4×4 · 162 pairs</td><td class="num">39.51%</td><td class="num">3.638×</td><td class="num">+190.89%</td><td class="num bad">10</td></tr>
      <tr><td>8×8 · 162 pairs</td><td class="num">34.95%</td><td class="num">3.472×</td><td class="num">+208.34%</td><td class="num good">0</td></tr>
    </tbody>
  </table>

  <div class="cap" style="text-align:left">Latency is geometric mean; link-flit reduction and throughput are arithmetic means. Medians: 41.18%/29.63% traffic and 3.588×/2.667× latency.</div>

  <div class="card cy">
    <span class="mark">WHY SOME 4×4 CASES ARE SLOWER</span>
    <h3>One blocked branch makes the others wait</h3>
    <p>All ten slower-than-unicast cases are fanout-4. When one output VC has no credit, multicast waits before sending that flit to any branch; the worst case is <b>−18.24%</b>.</p>
  </div>

</div>

</div>

</div>

<div class="take cy"><span class="lab">Reading</span>Link-flit saving is structural. Latency includes the dedicated Router datapath. Throughput exposes the cost of making all selected branches wait together.</div>

<!--
Timing 50 s. 这一页看 common fanout，也就是 4、8、16 目的地时的总体结果。左图的柱子表示 internal-link flit 少了多少；右表把 latency、throughput 和坏案例放在一起。4×4 平均少 39.51% 的 link flits，latency 是 3.638× speedup，throughput 提升 190.89%；8×8 分别是 34.95%、3.472× 和 208.34%。最后一列只统计 throughput 低于 unicast 的配对案例，不是 latency 变慢。4×4 有 10 个，全部是 fanout-4；原因是某个 output VC 没有 credit 时，multicast 要等这个分支，其他分支也不能先发这个 flit。8×8 没有这类案例。
-->
