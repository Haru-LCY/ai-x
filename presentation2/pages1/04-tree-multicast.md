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
现在我们看一下multicast的实现。这个图的左边是 baseline，右边是我们的 tree multicast。

先看 baseline。它采用 replicated unicast：Network Interface 会为每个远端 destination 注入一个独立 packet。这样一来，共享路径会重复传输相同的 payload，destination 越多，重复流量越大。

右边的 proposed path 只注入一个 packet，packet 携带 64-bit destination bitmap。每个 Router 根据 bitmap 判断哪些 child branch 仍然通向目标，只有确实需要多个方向时才复制 flit，本地 destination 则直接接收。因此，共享前缀只传一次，复制发生在树的分叉处。

这个设计的代价是一个 flit 只有在所有选中的 output VC 都有 credit 时才会同时前进。这样可以保证 multi-flit packet 完整、有序，并且每个 destination 只收到一次。相应地，只要有一个分支拥塞，其他分支也必须等待。
-->
