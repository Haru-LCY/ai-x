# Research background

<p class="lede">Modern AI training scales across many GPUs. Every training step must move and synchronize large tensors, making the interconnect part of the critical path.</p>

<div class="body bg-body">

<div class="training-flow">

  <div class="flow-node compute">
    <span class="node-tag">COMPUTE</span>
    <b>GPU ranks</b>
    <small>forward / backward</small>
  </div>

  <div class="flow-link">
    <span>gradient tensor</span>
    <i></i>
  </div>

  <div class="flow-node collective">
    <span class="node-tag">COMMUNICATE</span>
    <b>Collective operation</b>
    <small>all-reduce / broadcast</small>
  </div>

  <div class="flow-link">
    <span>synchronize</span>
    <i></i>
  </div>

  <div class="flow-node compute">
    <span class="node-tag">CONTINUE</span>
    <b>Next training step</b>
    <small>uses the global result</small>
  </div>

  <div class="study-focus">
    <i></i>
    <div>
      <b>OUR STUDY FOCUSES ON THIS LAYER</b>
      <small>Mesh NoC · router datapath · packets / flits</small>
    </div>
  </div>

</div>

<div class="study-grid">
  <div class="study-card">
    <span class="study-num">01</span>
    <div>
      <h3>Duplicated traffic</h3>
      <p><b>Tree multicast</b> shares common paths and replicates only at useful branches.</p>
    </div>
  </div>
  <div class="study-card">
    <span class="study-num">02</span>
    <div>
      <h3>Long multi-hop routes</h3>
      <p><b>Express-link bypass</b> skips intermediate routers when admission is safe.</p>
    </div>
  </div>
  <div class="study-card">
    <span class="study-num">03</span>
    <div>
      <h3>Real collective demand</h3>
      <p><b>H100 all-reduce replay</b> maps measured tensor events into network traffic.</p>
    </div>
  </div>
</div>

</div>

<div class="take"><span class="lab">Our scope</span>We implement and evaluate all three mechanisms at the network layer in gem5 Garnet.</div>

<style>
.bg-body {
  align-content: stretch;
  gap: 12px;
}

.training-flow {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 112px 1.16fr 112px 1fr;
  align-items: center;
  min-height: 230px;
  padding: 18px 26px 72px;
  background: linear-gradient(110deg, #f6f2f7 0%, #fff 48%, #faf6ed 100%);
  border-top: 2px solid var(--purple);
  border-bottom: 1px solid var(--line);
}

.flow-node {
  min-height: 92px;
  padding: 13px 15px 12px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border: 1px solid var(--line-strong);
  background: rgba(255, 255, 255, 0.86);
}

.flow-node.collective {
  border-color: rgba(102, 8, 116, 0.5);
  border-top: 3px solid var(--purple);
  background: #fff;
  box-shadow: 0 8px 24px rgba(83, 6, 95, 0.08);
}

.node-tag {
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.13em;
  color: var(--purple);
}

.flow-node b {
  margin-top: 3px;
  font-size: 17px;
  line-height: 1.2;
  color: var(--ink);
}

.flow-node small {
  margin-top: 3px;
  font-size: 12.5px;
  color: var(--dim);
}

.flow-link {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 7px;
}

.flow-link span {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10.5px;
  color: var(--dim);
  white-space: nowrap;
}

.flow-link i {
  position: relative;
  width: 76px;
  height: 2px;
  background: var(--purple);
}

.flow-link i::after {
  content: '';
  position: absolute;
  right: -1px;
  top: -4px;
  border-left: 8px solid var(--purple);
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
}

.study-focus {
  position: absolute;
  left: 50%;
  bottom: 11px;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
}

.study-focus > i {
  position: relative;
  width: 2px;
  height: 17px;
  background: var(--purple);
}

.study-focus > i::after {
  content: '';
  position: absolute;
  left: -4px;
  bottom: -1px;
  border-top: 7px solid var(--purple);
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
}

.study-focus > div {
  min-width: 306px;
  padding: 6px 14px 7px;
  background: var(--purple);
  color: white;
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1.2;
}

.study-focus b { font-size: 9.5px; letter-spacing: 0.12em; }
.study-focus small { margin-top: 2px; font-size: 10.5px; opacity: 0.8; }

.study-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 22px;
}

.study-card {
  display: grid;
  grid-template-columns: 34px 1fr;
  gap: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--line-strong);
}

.study-num {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 15px;
  font-weight: 600;
  color: var(--purple);
}

.study-card h3 {
  font-size: 15.5px;
  font-weight: 650;
  color: var(--ink);
}

.study-card p {
  margin-top: 3px;
  font-size: 12.7px;
  line-height: 1.35;
}

.study-card p b { color: var(--purple); }
</style>

<!--
Timing 35 s. GPU computation produces gradient tensors, collective communication synchronizes them, and the global result enables the next training step. Our study focuses on how those collectives become packets and flits in the Mesh NoC. We implement tree multicast, express-link bypass, and H100 all-reduce trace replay at this network layer.
-->
