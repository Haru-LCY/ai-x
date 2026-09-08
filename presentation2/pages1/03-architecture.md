# Research background

<p class="lede">Modern AI training scales across many GPUs. Every training step must move and synchronize large tensors, making the interconnect part of the critical path.</p>

<div class="body bg-body">

<div class="training-figure">
  <img src="/training_to_network.png" alt="Training computation and communication flow into the Mesh NoC" />
</div>

<div class="study-grid">
  <div class="study-card">
    <span class="study-num">01</span>
    <div>
      <h3>Shared-path delivery</h3>
      <p><b>Multicast delivery</b> shares common paths and replicates only where destinations split.</p>
    </div>
  </div>
  <div class="study-card">
    <span class="study-num">02</span>
    <div>
      <h3>Shorter network routes</h3>
      <p><b>Shortcut routing</b> skips intermediate routers when admission is safe.</p>
    </div>
  </div>
  <div class="study-card">
    <span class="study-num">03</span>
    <div>
      <h3>Measured workloads</h3>
      <p><b>Trace-driven replay</b> maps measured tensor events into network traffic.</p>
    </div>
  </div>
</div>

</div>

<div class="take"><span class="lab">Our scope</span>We implement and evaluate all three mechanisms at the network layer in gem5 Garnet.</div>

<!--
Timing 30 s. 先看动机。GPU 完成一轮 computation 后会产生 gradient tensors，collective communication 要把这些数据同步起来，完成后才能进入下一轮 training。图里从 training computation，到 collective，再到 Mesh NoC 中的 packets 和 flits。我们的研究范围就在这个 network layer，分别实现 multicast delivery、shortcut routing，以及 H100 all-reduce trace replay。
-->
