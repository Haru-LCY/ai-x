# Multicast scale-out

<p class="lede">Larger fanouts expose more shared prefixes.</p>

<div class="body" style="grid-template-rows:auto 1fr;gap:14px">

<div class="metrics">
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

  <div class="fig" style="height:260px"><img src="/latency_speedup_by_group.png" alt="Multicast latency speedup by topology, fanout, and packet size" /></div>
  <div class="cap">Scale-out means: +895.54% throughput at fanout 32 and +1,888.29% at fanout 64. These groups are not pooled with the common-fanout mean.</div>

</div>

</div>

<div class="take cy"><span class="lab">Interpretation</span>The gain grows because more destinations share prefixes. The scale-out numbers characterize 8×8; they are not a cross-topology average.</div>

<!--
Timing 30 s. The separate 8x8 scale-out study reaches 62.41 percent traffic reduction at fanout 32 and 75.39 percent at fanout 64. Latency speedups are 11.25x and 21.62x. We keep these groups separate from the common-fanout comparison.
-->
