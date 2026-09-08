# Conclusion

<p class="lede">Three results, three separate claims.</p>

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
Timing 30 s. 最后把三条结论分开看。第一，tree multicast 的收益来自 structural sharing，fanout 越大越明显，但小规模 4×4 仍可能因为 atomic branch waiting 出现吞吐低于 unicast 的案例。第二，pressure-aware bypass 能降低 latency 和 Router traversal，但这里评估的是 dense stride-2 arm，它增加了 links、ports、wire span 和 buffers，所以结论是 useful, not free，也不是直接的硬件性价比结论。第三，tensor all-reduce 说明 representation matters：保留 event-level structure，就能消除 scalar serialization，而不改变 flit 数量。统一的 design principle 是，只在能证明减少 network work 或 request serialization 时，才把 collective structure 暴露给 network。
-->
