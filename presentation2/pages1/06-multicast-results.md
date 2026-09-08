# Multicast results

<p class="lede">Common-fanout gains, with slower cases retained.</p>

<div class="body">

<div class="grid2">

<div>

  <div class="fig" style="height:275px"><img src="/traffic_reduction_by_group.png" alt="Internal-link flit reduction by topology and destination count" /></div>
  <div class="cap">Each bar averages the 1-, 4-, and 16-flit packet cases. 4×4 and 8×8 common-fanout results are reported separately; fanout 32 and 64 are scale-out only.</div>

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
这一页报告了我们multicast的所有实验，我们在在4x4 8x8两种mesh上做了实验，fanout是4,8,16,对于8x8我们还额外做了fanout为32，64的。
表格和figure中的数值报告的都是1,4,16 flit packet的平均值。表格中报告了latency和throughput的平均值和比unicast更慢的case的数量。

先看 4×4。平均减少 39.51% 的 link flits，latency 是 3.638× speedup，throughput 提升 190.89%。8×8 也减少 34.95% 的 link flits，latency 是 3.472×，throughput 提升 208.34%。这里 latency 使用 geometric mean，link-flit reduction 和 throughput 使用 arithmetic mean。

最后看右侧的 slower cases。4×4 有 10 个，8×8 是 0 个。这里统计的是 throughput 低于 unicast 的配对案例，不是 latency 变慢；而且这 10 个案例全部来自 fanout-4。原因和上一页的 atomic fanout 一致：某个 output VC 没有 credit 时，当前 flit 必须等所有分支一起发送，其他本来可用的分支也不能先走。最差的案例是下降 18.24%。

所以，tree multicast 的收益来自 structural sharing，但在小 fanout 和拥塞条件下，atomic synchronization 可能抵消一部分 throughput 收益。
-->
