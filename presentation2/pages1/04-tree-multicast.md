# Tree multicast

<p class="lede">Replicate inside pruned-tree branches.</p>

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
Timing 40 s. 先看 tree multicast。Baseline 是 replicated unicast：NI 给每个远端 destination 注入一个独立 packet，所以共享路径会重复搬运同样的 payload。Proposed 只发送一个带 64-bit destination bitmap 的 packet，沿途每个 Router 只保留真正通向 destination 的 branches，需要分叉时才复制。这里的 tradeoff 是 atomic fanout：一个 flit 要等所有选中的 output VC 都有 credit 才能一起前进。这样能保证多 flit packet 完整且有序，但一个拥塞分支可能让其他分支也等待。
-->
