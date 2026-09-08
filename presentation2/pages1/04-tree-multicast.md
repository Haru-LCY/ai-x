# Tree multicast

<p class="lede">Send one packet down a tree; copy only where paths split.</p>

<div class="body">

<div class="grid2 rev">

<div class="stack">

  <div class="card">
    <span class="mark">BASELINE</span>
    <h3>Replicated unicast</h3>
    <p>The NI injects one packet per remote destination and records a selected local destination. Shared path prefixes carry the same payload repeatedly.</p>
  </div>

  <div class="card cy">
    <span class="mark">PROPOSED</span>
    <h3>One bitmap packet</h3>
    <p>A 64-bit destination bitmap travels in the head flit. Each Router computes only the child branches that still lead to a destination and delivers locally when selected.</p>
  </div>

  <div class="card cy">
    <span class="mark">TRADEOFF</span>
    <h3>Exact, but synchronized</h3>
    <p>Fanout is atomic: a flit advances only after every selected output VC has credit. This preserves multi-flit delivery, but a blocked branch can hold the others.</p>
  </div>

</div>

<div>

  <div class="figpair">
    <div>
      <div class="fig" style="height:285px"><img src="/multicast_baseline_4x4.png" alt="Replicated-unicast baseline on a four-by-four mesh" /></div>
      <div class="cap"><b>(a)</b> Replicated-unicast baseline</div>
    </div>
    <div>
      <div class="fig" style="height:285px"><img src="/multicast_tree_4x4.png" alt="Proposed pruned-tree multicast path on a four-by-four mesh" /></div>
      <div class="cap"><b>(b)</b> Proposed tree multicast</div>
    </div>
  </div>
  <div class="cap">Illustrative 4×4 multicast baseline and proposed path.</div>

</div>

</div>

</div>

<div class="take cy"><span class="lab">Correctness contract</span>Every destination receives the complete packet exactly once, in flit order, with no missing or duplicate delivery.</div>

<!--
现在看 multicast 的实现。左边的 baseline 是 replicated unicast：Network Interface 为每个远端 destination 注入一个独立 packet，共享路径会重复传输相同的 payload。

右边的 tree multicast 只注入一个带 64-bit destination bitmap 的 packet。每个 Router 根据 bitmap 保留仍然通向目标的 child branches，需要分叉时才复制 flit，本地 destination 则直接接收。这样共享前缀只传一次，复制只发生在树的分叉处。
-->
