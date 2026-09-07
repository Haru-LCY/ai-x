# Conclusion

<p class="lede">Three claims, kept separate.</p>

<div class="body">

<div class="cards3">
  <div class="card cy">
    <span class="mark">TREE MULTICAST</span>
    <h3>Sharing is structural</h3>
    <p>Common-fanout traffic falls 39.51% on 4×4 and 34.95% on 8×8; scale-out reaches 75.39% at fanout 64. Atomic fanout explains the ten 4×4 regressions.</p>
  </div>
  <div class="card am">
    <span class="mark">PRESSURE-AWARE BYPASS</span>
    <h3>Useful, not free</h3>
    <p>Distance-scaled stride links give 1.291× and 1.583× mean latency speedup, with explicit added links, ports, wire span, and buffer proxies.</p>
  </div>
  <div class="card vi">
    <span class="mark">TENSOR ALL-REDUCE</span>
    <h3>Representation matters</h3>
    <p>Event-level requests finish the scaled trace 4.728× sooner while injecting and forwarding exactly the same flit counts.</p>
  </div>
</div>

</div>

<div class="take"><span class="lab">Design principle</span>Expose collective structure only where it removes demonstrable network work or request serialization; keep every claim beside its matched baseline and its resource boundary.</div>

<!--
Timing 25 s. Multicast removes duplicated link work, especially at high fanout. Bypass improves latency with added hardware and conservative admission. Tensor streaming preserves event structure and removes scalar serialization.
-->
