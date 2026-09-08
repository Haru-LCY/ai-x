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
我们的选题背景是，当前 AI 大模型训练普遍采用 GPU 集群。每一轮训练都需要在 GPU 之间传输并同步大量 tensor 数据，因此 interconnect 已成为影响训练效率的关键路径之一。图中展示了数据从 training computation 产生，经过 collective communication，最终在 Mesh NoC 中以 packets 和 flits 的形式传输的过程。我们的研究聚焦于 network layer，分别实现并评估 multicast、bypass，以及 H100 all-reduce trace replay。
-->
