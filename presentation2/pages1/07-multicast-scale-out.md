# Higher fanout, stronger speedup

<p class="lede">As fanout grows, multicast gains become more pronounced.</p>

<div class="body scaleout-body" style="grid-template-rows:auto 1fr;gap:8px">

<div class="metrics scaleout-metrics">
  <div class="metric cy">
    <span class="v">−62.41%</span>
    <span class="k">link flits at fanout 32</span>
    <span class="n">8×8 scale-out study</span>
  </div>
  <div class="metric cy">
    <span class="v">11.25×</span>
    <span class="k">geometric-mean latency speedup</span>
    <span class="n">fanout 32</span>
  </div>
  <div class="metric cy">
    <span class="v">−75.39%</span>
    <span class="k">link flits at fanout 64</span>
    <span class="n">8×8 scale-out study</span>
  </div>
  <div class="metric cy">
    <span class="v">21.62×</span>
    <span class="k">geometric-mean latency speedup</span>
    <span class="n">fanout 64</span>
  </div>
</div>

<div>

  <div class="fig" style="height:320px"><img src="/latency_speedup_by_group.png" alt="Multicast latency speedup by topology, fanout, and packet size" /></div>
  <div class="cap">Scale-out means: +895.54% throughput at fanout 32 and +1,888.29% at fanout 64. These groups are not pooled with the common-fanout mean.</div>

</div>

</div>

<div class="take take-focus cy">Overall, larger fanout makes multicast speedups more pronounced.</div>

<!--
Timing 30 s. 接着把 fanout 从常见的 4、8、16 扩大到 32 和 64。这里是单独的 8×8 scale-out study，不和前面的 common-fanout 平均值混合。fanout 32 时 link flits 少 62.41%，latency 是 11.25×；fanout 64 时分别达到 75.39% 和 21.62×。右图还按 packet size 区分 1、4、16 flits。总体结论很简单：fanout 越大，更多目的地可以共享同一棵树，multicast 的加速越明显。
-->
