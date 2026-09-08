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
我们的选题背景是，当前 AI 大模型训练普遍采用 GPU 集群。每一轮训练都需要在 GPU 之间传输并同步大量 tensor 数据，因此 interconnect 已成为影响训练效率的关键路径之一。图中展示了数据从 training computation 产生，经过 collective communication，最终在 Mesh NoC 中以 packets 和 flits 的形式传输的过程。我们的研究聚焦于 network layer，主要实现了 multicast和bypass，还有一个trace-based tensor all reduce。

（可不可以改成：我们的选题背景是 AI 训练需要在大量计算单元之间同步 tensor——这些单元可能是同芯片的加速引擎、同封装的 die，也可能是集群里的 GPU。无论哪一层，集合通信最终都要经过一个互连网络，interconnect 因此成为训练效率的关键路径之一。我们的做法是把这类通信模式抽象成网络流量，放到 gem5 Garnet 这个片上网络模型里，在 network layer 研究 multicast、bypass 和 trace-based all-reduce。图中就是数据从计算产生、经过 collective communication、最终在 mesh 里变成packets/flits 传输的过程。）
-->
