/*
 * Copyright (c) 2020 Advanced Micro Devices, Inc.
 * Copyright (c) 2008 Princeton University
 * Copyright (c) 2016 Georgia Institute of Technology
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are
 * met: redistributions of source code must retain the above copyright
 * notice, this list of conditions and the following disclaimer;
 * redistributions in binary form must reproduce the above copyright
 * notice, this list of conditions and the following disclaimer in the
 * documentation and/or other materials provided with the distribution;
 * neither the name of the copyright holders nor the names of its
 * contributors may be used to endorse or promote products derived from
 * this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */


#include "mem/ruby/network/garnet/GarnetNetwork.hh"

#include <algorithm>
#include <cassert>

#include "base/cast.hh"
#include "base/compiler.hh"
#include "debug/RubyNetwork.hh"
#include "mem/ruby/common/NetDest.hh"
#include "mem/ruby/network/MessageBuffer.hh"
#include "mem/ruby/network/garnet/CommonTypes.hh"
#include "mem/ruby/network/garnet/CreditLink.hh"
#include "mem/ruby/network/garnet/GarnetLink.hh"
#include "mem/ruby/network/garnet/NetworkInterface.hh"
#include "mem/ruby/network/garnet/NetworkLink.hh"
#include "mem/ruby/network/garnet/Router.hh"
#include "mem/ruby/system/RubySystem.hh"
#include "sim/sim_exit.hh"

namespace gem5
{

namespace ruby
{

namespace garnet
{

/*
 * GarnetNetwork sets up the routers and links and collects stats.
 * Default parameters (GarnetNetwork.py) can be overwritten from command line
 * (see configs/network/Network.py)
 */

GarnetNetwork::GarnetNetwork(const Params &p)
    : Network(p)
{
    m_num_rows = p.num_rows;
    m_ni_flit_size = p.ni_flit_size;
    m_max_vcs_per_vnet = 0;
    m_buffers_per_data_vc = p.buffers_per_data_vc;
    m_buffers_per_ctrl_vc = p.buffers_per_ctrl_vc;
    m_routing_algorithm = p.routing_algorithm;
    m_bypass_first_hops = p.bypass_first_hops;
    m_bypass_first_hop_destinations = p.bypass_first_hop_destinations;
    m_bypass_link_ids = p.bypass_link_ids;
    m_bypass_link_spans = p.bypass_link_spans;
    m_synthetic_packet_flits = p.synthetic_packet_flits;
    fatal_if(m_synthetic_packet_flits < 0,
             "Synthetic packet flits cannot be negative");
    fatal_if(m_bypass_link_ids.size() != m_bypass_link_spans.size(),
             "Bypass link id/span vectors differ: %d != %d",
             (int)m_bypass_link_ids.size(), (int)m_bypass_link_spans.size());
    fatal_if(!m_bypass_first_hop_destinations.empty() &&
             m_bypass_first_hop_destinations.size() !=
                 m_bypass_first_hops.size(),
             "Bypass first-hop destination/name vectors differ");
    m_collective_mode = p.collective_mode;
    m_collective_multicast = p.collective_multicast;
    m_collective_tensor = p.collective_tensor;
    m_collective_rounds = p.collective_rounds;
    m_multicast_mode = p.multicast_mode;
    m_multicast_source = p.multicast_source;
    m_multicast_packet_flits = p.multicast_packet_flits;
    m_collective_vnet = p.collective_vnet;
    m_multicast_workload = p.multicast_workload;
    m_multicast_max_outstanding = p.multicast_max_outstanding;
    m_multicast_warmup_rounds = p.multicast_warmup_rounds;
    m_multicast_measurement_rounds = p.multicast_measurement_rounds;
    m_multicast_cooldown_rounds = p.multicast_cooldown_rounds;
    fatal_if(m_collective_rounds < 1,
             "Lab4 collective rounds must be positive");
    m_next_packet_id = 0;

    m_enable_fault_model = p.enable_fault_model;
    if (m_enable_fault_model)
        fault_model = p.fault_model;

    m_vnet_type.resize(m_virtual_networks);

    for (int i = 0 ; i < m_virtual_networks ; i++) {
        if (m_vnet_type_names[i] == "response")
            m_vnet_type[i] = DATA_VNET_; // carries data (and ctrl) packets
        else
            m_vnet_type[i] = CTRL_VNET_; // carries only ctrl packets
    }

    // record the routers
    for (std::vector<BasicRouter*>::const_iterator i =  p.routers.begin();
         i != p.routers.end(); ++i) {
        Router* router = safe_cast<Router*>(*i);
        m_routers.push_back(router);

        // initialize the router's network pointers
        router->init_net_ptr(this);
    }
    m_collective_round_states.resize(m_collective_rounds);
    for (auto& state : m_collective_round_states)
        state.delivered.assign(m_routers.size(), false);
    m_multicast_destinations.assign(m_routers.size(), false);
    fatal_if(m_multicast_mode != "none" &&
             m_multicast_mode != "naive_unicast" &&
             m_multicast_mode != "tree_multicast",
             "Invalid multicast mode '%s'", m_multicast_mode.c_str());
    fatal_if(m_collective_multicast && m_multicast_mode == "none",
             "Collective multicast requires an explicit multicast mode");
    fatal_if(m_multicast_mode != "none" &&
             (m_multicast_source < 0 || m_multicast_source >= getNumRouters()),
             "Invalid multicast source Router %d", m_multicast_source);
    fatal_if(m_multicast_mode != "none" && getNumRouters() > 64,
             "Multicast destination bitmap supports at most 64 Routers");
    fatal_if(m_multicast_mode != "none" && m_multicast_packet_flits < 1,
             "Multicast packet must contain at least one flit");
    fatal_if(m_multicast_mode != "none" &&
             m_multicast_workload != "latency" &&
             m_multicast_workload != "throughput",
             "Invalid multicast workload '%s'",
             m_multicast_workload.c_str());
    fatal_if(m_multicast_max_outstanding < 1,
             "Multicast max outstanding must be positive");
    for (const int destination : p.multicast_destinations) {
        fatal_if(destination < 0 || destination >= getNumRouters(),
                 "Invalid multicast destination Router %d", destination);
        fatal_if(m_multicast_destinations[destination],
                 "Duplicate multicast destination Router %d", destination);
        m_multicast_destinations[destination] = true;
        m_multicast_destination_mask |= uint64_t(1) << destination;
        ++m_multicast_destination_count;
    }
    fatal_if(m_multicast_mode != "none" && m_multicast_destination_count == 0,
             "Multicast destination set must not be empty");

    // record the network interfaces
    for (std::vector<ClockedObject*>::const_iterator i = p.netifs.begin();
         i != p.netifs.end(); ++i) {
        NetworkInterface *ni = safe_cast<NetworkInterface *>(*i);
        m_nis.push_back(ni);
        ni->init_net_ptr(this);
    }

    // Print Garnet version
    inform("Garnet version %s\n", garnetVersion);
}

bool
GarnetNetwork::canInjectCollectiveRound(int collective_id) const
{
    return collective_id == m_collective_next_injection_id &&
           m_collective_active_rounds < m_multicast_max_outstanding;
}

void
GarnetNetwork::recordMulticastInternalLinkFlit(int collective_id)
{
    ++m_multicast_internal_link_flits;
    if (isMeasurementRound(collective_id))
        ++m_multicast_measured_internal_link_flits;
}

int
GarnetNetwork::nextNaiveMulticastRound()
{
    fatal_if(!naiveMulticast(),
             "Naive packet round requested outside naive multicast");
    const int remote_destinations = m_multicast_destination_count -
        (multicastDestination(m_multicast_source) ? 1 : 0);
    fatal_if(remote_destinations == 0,
             "Local-only multicast must not inject a physical packet");
    const int round = m_naive_injection_round;
    if (++m_naive_packets_in_round == remote_destinations) {
        m_naive_packets_in_round = 0;
        ++m_naive_injection_round;
    }
    return round;
}

bool
GarnetNetwork::multicastDestination(int router_id) const
{
    return router_id >= 0 && router_id < m_multicast_destinations.size() &&
           m_multicast_destinations[router_id];
}

bool
GarnetNetwork::multicastDestination(uint64_t destinations,
                                    int router_id) const
{
    return router_id >= 0 && router_id < 64 &&
           (destinations & (uint64_t(1) << router_id));
}

bool
GarnetNetwork::multicastChildNeeded(uint64_t destinations, int router_id,
                                    int child_id) const
{
    fatal_if(!treeMulticast(), "Tree branch query outside tree multicast");
    const int cols = m_num_cols;
    const auto& bypass_first_hops = m_bypass_first_hop_destinations;
    const bool use_bypass_tree = bypass_first_hops.size() ==
        m_routers.size() * m_routers.size();
    const auto xy_next = [cols](int node, int destination) {
        const int x = node % cols;
        const int dest_x = destination % cols;
        if (x != dest_x)
            return node + (dest_x > x ? 1 : -1);
        return node + (destination > node ? cols : -cols);
    };
    for (int destination = 0;
         destination < m_multicast_destinations.size(); ++destination) {
        if (!multicastDestination(destinations, destination))
            continue;
        bool use_express = use_bypass_tree && bypass_first_hops[
            m_multicast_source * m_routers.size() + destination] >= 0;
        if (use_express) {
            // Keep the ordinary XY branch when another destination already
            // uses any edge on this destination's XY path. In that case the
            // express edge would destroy tree sharing and increase wire cost.
            for (int other = 0; other < m_multicast_destinations.size() &&
                 use_express; ++other) {
                if (other == destination ||
                    !multicastDestination(destinations, other))
                    continue;
                int candidate_node = m_multicast_source;
                while (candidate_node != destination && use_express) {
                    const int candidate_next =
                        xy_next(candidate_node, destination);
                    int other_node = m_multicast_source;
                    while (other_node != other) {
                        const int other_next = xy_next(other_node, other);
                        if (candidate_node == other_node &&
                            candidate_next == other_next) {
                            use_express = false;
                            break;
                        }
                        other_node = other_next;
                    }
                    candidate_node = candidate_next;
                }
            }
        }
        int node = m_multicast_source;
        while (node != destination) {
            const int x = node % cols;
            int next;
            if (use_express && node == m_multicast_source) {
                // The deterministic bypass oracle uses an express link only
                // on the source's first hop; all later hops are XY.
                next = bypass_first_hops[
                    m_multicast_source * m_routers.size() + destination];
                if (next < 0)
                    next = xy_next(node, destination);
            } else if (x != destination % cols) {
                next = xy_next(node, destination);
            } else {
                next = xy_next(node, destination);
            }
            if (node == router_id && next == child_id)
                return true;
            node = next;
        }
    }
    return false;
}

void
GarnetNetwork::recordCollectiveDelivery(int collective_id, int dest_router,
                                        int lane)
{
    fatal_if(!m_collective_mode,
             "Lab4 delivery recorded while collective mode is disabled");
    fatal_if(collective_id < 0 || collective_id >= m_collective_rounds,
             "Lab4 delivery has invalid round %d", collective_id);
    fatal_if(dest_router < 0 || dest_router >= getNumRouters(),
             "Lab4 delivery has invalid destination Router %d", dest_router);
    CollectiveRoundState& state = m_collective_round_states[collective_id];
    fatal_if(!state.started,
             "Lab4 delivery for round %d before injection", collective_id);

    if (m_collective_tensor) {
        fatal_if(lane < 0,
                 "Lab4 tensor delivery for round %d requires a lane id",
                 collective_id);
        fatal_if(state.tensor_lanes < 1,
                 "Lab4 tensor round %d has no lane count", collective_id);
        const auto dl = std::make_pair(dest_router, lane);
        fatal_if(state.tensor_delivered.count(dl),
                 "Lab4 duplicate tensor delivery round=%d dest=%d lane=%d",
                 collective_id, dest_router, lane);
        state.tensor_delivered.insert(dl);
        ++state.tensor_deliveries;
        ++m_collective_tensor_lanes_delivered;
        ++m_collective_deliveries;
        const int expected_deliveries =
            getNumRouters() * state.tensor_lanes;
        if (state.tensor_deliveries == expected_deliveries) {
            state.completed = true;
            --m_collective_active_rounds;
            ++m_collective_completed_rounds;
            const Tick latency = curTick() - state.start_tick;
            ++m_collective_rounds_completed;
            m_collective_completion_ticks += latency;
            ++m_collective_tensor_requests_completed;
            m_tensor_request_latencies.push_back(latency);
            inform("Lab4 tensor collective %d delivered %d lanes to all "
                   "%d routers in %llu ticks\n", collective_id,
                   state.tensor_lanes, getNumRouters(), latency);
            while (m_collective_delivery_id < m_collective_rounds &&
                   m_collective_round_states[
                       m_collective_delivery_id].completed)
                ++m_collective_delivery_id;
            if (m_collective_completed_rounds == m_collective_rounds) {
                if (!m_tensor_request_latencies.empty()) {
                    std::sort(m_tensor_request_latencies.begin(),
                              m_tensor_request_latencies.end());
                    const auto percentile = [&](size_t p) {
                        const size_t index =
                            (p * m_tensor_request_latencies.size() + 99) /
                                100 - 1;
                        return m_tensor_request_latencies[index];
                    };
                    m_collective_tensor_p50_completion_ticks =
                        percentile(50);
                    m_collective_tensor_p95_completion_ticks =
                        percentile(95);
                    m_collective_tensor_p99_completion_ticks =
                        percentile(99);
                }
                m_tensor_last_completion_tick = curTick();
                m_collective_tensor_measurement_ticks =
                    m_tensor_last_completion_tick -
                    m_tensor_first_injection_tick;
                size_t peak = 0;
                for (const auto* router : m_routers)
                    peak = std::max(peak, router->collectivePeakLanes());
                m_collective_tensor_peak_lanes = peak;
                exitSimLoop("Lab4 collective completed");
            }
        }
        return;
    }

    fatal_if(state.delivered[dest_router],
             "Lab4 duplicate delivery for round %d at Router %d",
             collective_id, dest_router);
    fatal_if(m_collective_multicast && !multicastDestination(dest_router),
             "Lab4 unexpected multicast delivery for round %d at Router %d",
             collective_id, dest_router);

    state.delivered[dest_router] = true;
    ++state.delivery_count;
    ++m_collective_deliveries;
    m_multicast_destination_latency_ticks += curTick() - state.start_tick;
    const int expected_deliveries = m_collective_multicast ?
        m_multicast_destination_count : getNumRouters();
    if (state.delivery_count == expected_deliveries) {
        state.completed = true;
        --m_collective_active_rounds;
        ++m_collective_completed_rounds;
        const Tick latency = curTick() - state.start_tick;
        ++m_collective_rounds_completed;
        m_collective_completion_ticks += latency;
        m_multicast_min_latency = std::min(m_multicast_min_latency, latency);
        m_multicast_max_latency = std::max(m_multicast_max_latency, latency);
        m_multicast_min_completion_ticks = m_multicast_min_latency;
        m_multicast_max_completion_ticks = m_multicast_max_latency;
        m_multicast_last_completion_tick = curTick();
        if (isMeasurementRound(collective_id)) {
            ++m_multicast_measured_requests;
            m_multicast_measured_completion_ticks += latency;
            m_multicast_measured_latencies.push_back(latency);
            m_multicast_measurement_last_completion_tick = curTick();
        }
        if (expected_deliveries == getNumRouters()) {
            inform("Lab4 collective round %d delivered to all %d routers "
                   "in %llu ticks\n", collective_id, expected_deliveries,
                   latency);
        } else {
            inform("Lab4 collective round %d delivered to all %d "
                   "destinations in %llu ticks\n", collective_id,
                   expected_deliveries, latency);
        }
        while (m_collective_delivery_id < m_collective_rounds &&
               m_collective_round_states[m_collective_delivery_id].completed)
            ++m_collective_delivery_id;
        if (m_collective_completed_rounds == m_collective_rounds) {
            if (!m_multicast_measured_latencies.empty()) {
                std::sort(m_multicast_measured_latencies.begin(),
                          m_multicast_measured_latencies.end());
                const size_t p95_index =
                    (95 * m_multicast_measured_latencies.size() + 99) / 100 - 1;
                m_multicast_p95_completion_ticks =
                    m_multicast_measured_latencies[p95_index];
            }
            m_multicast_measurement_ticks =
                m_multicast_measurement_last_completion_tick -
                m_multicast_measurement_first_injection_tick;
            exitSimLoop("Lab4 collective completed");
        }
    }
}

void
GarnetNetwork::setCollectiveRoundTensorLanes(int collective_id, int lanes)
{
    fatal_if(!m_collective_tensor,
             "Tensor round metadata set outside tensor mode");
    fatal_if(collective_id < 0 || collective_id >= m_collective_rounds,
             "Lab4 tensor round %d is invalid", collective_id);
    fatal_if(lanes < 1,
             "Lab4 tensor round %d must contain at least one lane",
             collective_id);
    m_collective_round_states[collective_id].tensor_lanes = lanes;
}

void
GarnetNetwork::beginCollectiveRound(int collective_id)
{
    fatal_if(collective_id < 0 || collective_id >= m_collective_rounds,
             "Lab4 attempted to start invalid round %d", collective_id);
    CollectiveRoundState& state = m_collective_round_states[collective_id];
    if (state.started)
        return;
    fatal_if(!canInjectCollectiveRound(collective_id),
             "Lab4 cannot start round %d with %d active rounds",
             collective_id, m_collective_active_rounds);
    state.started = true;
    state.start_tick = curTick();
    ++m_collective_next_injection_id;
    ++m_collective_active_rounds;
    if (m_collective_next_injection_id == 1)
        m_multicast_first_injection_tick = curTick();
    if (m_collective_tensor && collective_id == 0)
        m_tensor_first_injection_tick = curTick();
    if (collective_id == m_multicast_warmup_rounds)
        m_multicast_measurement_first_injection_tick = curTick();
    if (m_collective_multicast)
        ++m_multicast_logical_requests;
}

void
GarnetNetwork::recordMulticastLocalDelivery(int collective_id)
{
    fatal_if(!naiveMulticast(),
             "Local multicast completion is only valid for naive unicast");
    recordCollectiveDelivery(collective_id, m_multicast_source);
}

void
GarnetNetwork::recordCollectiveInjection(int collective_id, int source_flits)
{
    beginCollectiveRound(collective_id);
    m_collective_source_flits += source_flits;
    if (m_collective_multicast)
        ++m_multicast_physical_packets;
}

void
GarnetNetwork::init()
{
    Network::init();

    for (int i=0; i < m_nodes; i++) {
        m_nis[i]->addNode(m_toNetQueues[i], m_fromNetQueues[i]);
    }

    // The topology pointer should have already been initialized in the
    // parent network constructor
    assert(m_topology_ptr != NULL);
    m_topology_ptr->createLinks(this);

    // Initialize topology specific parameters
    if (getNumRows() > 0) {
        // Only for Mesh topology
        // m_num_rows and m_num_cols are only used for
        // implementing XY or custom routing in RoutingUnit.cc
        m_num_rows = getNumRows();
        m_num_cols = m_routers.size() / m_num_rows;
        assert(m_num_rows * m_num_cols == m_routers.size());
    } else {
        m_num_rows = -1;
        m_num_cols = -1;
    }

    // FaultModel: declare each router to the fault model
    if (isFaultModelEnabled()) {
        for (std::vector<Router*>::const_iterator i= m_routers.begin();
             i != m_routers.end(); ++i) {
            Router* router = safe_cast<Router*>(*i);
            [[maybe_unused]] int router_id =
                fault_model->declare_router(router->get_num_inports(),
                                            router->get_num_outports(),
                                            router->get_vc_per_vnet(),
                                            getBuffersPerDataVC(),
                                            getBuffersPerCtrlVC());
            assert(router_id == router->get_id());
            router->printAggregateFaultProbability(std::cout);
            router->printFaultVector(std::cout);
        }
    }
}

/*
 * This function creates a link from the Network Interface (NI)
 * into the Network.
 * It creates a Network Link from the NI to a Router and a Credit Link from
 * the Router to the NI
*/

void
GarnetNetwork::makeExtInLink(NodeID global_src, SwitchID dest, BasicLink* link,
                             std::vector<NetDest>& routing_table_entry)
{
    NodeID local_src = getLocalNodeID(global_src);
    assert(local_src < m_nodes);

    GarnetExtLink* garnet_link = safe_cast<GarnetExtLink*>(link);

    // GarnetExtLink is bi-directional
    NetworkLink* net_link = garnet_link->m_network_links[LinkDirection_In];
    net_link->setType(EXT_IN_);
    CreditLink* credit_link = garnet_link->m_credit_links[LinkDirection_In];

    m_networklinks.push_back(net_link);
    m_creditlinks.push_back(credit_link);

    PortDirection dst_inport_dirn = "Local";

    m_max_vcs_per_vnet = std::max(m_max_vcs_per_vnet,
                             m_routers[dest]->get_vc_per_vnet());

    /*
     * We check if a bridge was enabled at any end of the link.
     * The bridge is enabled if either of clock domain
     * crossing (CDC) or Serializer-Deserializer(SerDes) unit is
     * enabled for the link at each end. The bridge encapsulates
     * the functionality for both CDC and SerDes and is a Consumer
     * object similiar to a NetworkLink.
     *
     * If a bridge was enabled we connect the NI and Routers to
     * bridge before connecting the link. Example, if an external
     * bridge is enabled, we would connect:
     * NI--->NetworkBridge--->GarnetExtLink---->Router
     */
    if (garnet_link->extBridgeEn) {
        DPRINTF(RubyNetwork, "Enable external bridge for %s\n",
            garnet_link->name());
        NetworkBridge *n_bridge = garnet_link->extNetBridge[LinkDirection_In];
        m_nis[local_src]->
        addOutPort(n_bridge,
                   garnet_link->extCredBridge[LinkDirection_In],
                   dest, m_routers[dest]->get_vc_per_vnet());
        m_networkbridges.push_back(n_bridge);
    } else {
        m_nis[local_src]->addOutPort(net_link, credit_link, dest,
            m_routers[dest]->get_vc_per_vnet());
    }

    if (garnet_link->intBridgeEn) {
        DPRINTF(RubyNetwork, "Enable internal bridge for %s\n",
            garnet_link->name());
        NetworkBridge *n_bridge = garnet_link->intNetBridge[LinkDirection_In];
        m_routers[dest]->
            addInPort(dst_inport_dirn,
                      n_bridge,
                      garnet_link->intCredBridge[LinkDirection_In]);
        m_networkbridges.push_back(n_bridge);
    } else {
        m_routers[dest]->addInPort(dst_inport_dirn, net_link, credit_link);
    }

}

/*
 * This function creates a link from the Network to a NI.
 * It creates a Network Link from a Router to the NI and
 * a Credit Link from NI to the Router
*/

void
GarnetNetwork::makeExtOutLink(SwitchID src, NodeID global_dest,
                              BasicLink* link,
                              std::vector<NetDest>& routing_table_entry)
{
    NodeID local_dest = getLocalNodeID(global_dest);
    assert(local_dest < m_nodes);
    assert(src < m_routers.size());
    assert(m_routers[src] != NULL);

    GarnetExtLink* garnet_link = safe_cast<GarnetExtLink*>(link);

    // GarnetExtLink is bi-directional
    NetworkLink* net_link = garnet_link->m_network_links[LinkDirection_Out];
    net_link->setType(EXT_OUT_);
    CreditLink* credit_link = garnet_link->m_credit_links[LinkDirection_Out];

    m_networklinks.push_back(net_link);
    m_creditlinks.push_back(credit_link);

    PortDirection src_outport_dirn = "Local";

    m_max_vcs_per_vnet = std::max(m_max_vcs_per_vnet,
                             m_routers[src]->get_vc_per_vnet());

    /*
     * We check if a bridge was enabled at any end of the link.
     * The bridge is enabled if either of clock domain
     * crossing (CDC) or Serializer-Deserializer(SerDes) unit is
     * enabled for the link at each end. The bridge encapsulates
     * the functionality for both CDC and SerDes and is a Consumer
     * object similiar to a NetworkLink.
     *
     * If a bridge was enabled we connect the NI and Routers to
     * bridge before connecting the link. Example, if an external
     * bridge is enabled, we would connect:
     * NI<---NetworkBridge<---GarnetExtLink<----Router
     */
    if (garnet_link->extBridgeEn) {
        DPRINTF(RubyNetwork, "Enable external bridge for %s\n",
            garnet_link->name());
        NetworkBridge *n_bridge = garnet_link->extNetBridge[LinkDirection_Out];
        m_nis[local_dest]->
            addInPort(n_bridge, garnet_link->extCredBridge[LinkDirection_Out]);
        m_networkbridges.push_back(n_bridge);
    } else {
        m_nis[local_dest]->addInPort(net_link, credit_link);
    }

    if (garnet_link->intBridgeEn) {
        DPRINTF(RubyNetwork, "Enable internal bridge for %s\n",
            garnet_link->name());
        NetworkBridge *n_bridge = garnet_link->intNetBridge[LinkDirection_Out];
        m_routers[src]->
            addOutPort(src_outport_dirn,
                       n_bridge,
                       routing_table_entry, link->m_weight,
                       garnet_link->intCredBridge[LinkDirection_Out],
                       m_routers[src]->get_vc_per_vnet());
        m_networkbridges.push_back(n_bridge);
    } else {
        m_routers[src]->
            addOutPort(src_outport_dirn, net_link,
                       routing_table_entry,
                       link->m_weight, credit_link,
                       m_routers[src]->get_vc_per_vnet());
    }
}

/*
 * This function creates an internal network link between two routers.
 * It adds both the network link and an opposite credit link.
*/

void
GarnetNetwork::makeInternalLink(SwitchID src, SwitchID dest, BasicLink* link,
                                std::vector<NetDest>& routing_table_entry,
                                PortDirection src_outport_dirn,
                                PortDirection dst_inport_dirn)
{
    GarnetIntLink* garnet_link = safe_cast<GarnetIntLink*>(link);

    // GarnetIntLink is unidirectional
    NetworkLink* net_link = garnet_link->m_network_link;
    net_link->setType(INT_);
    CreditLink* credit_link = garnet_link->m_credit_link;

    m_networklinks.push_back(net_link);
    m_creditlinks.push_back(credit_link);

    m_max_vcs_per_vnet = std::max(m_max_vcs_per_vnet,
                             std::max(m_routers[dest]->get_vc_per_vnet(),
                             m_routers[src]->get_vc_per_vnet()));

    /*
     * We check if a bridge was enabled at any end of the link.
     * The bridge is enabled if either of clock domain
     * crossing (CDC) or Serializer-Deserializer(SerDes) unit is
     * enabled for the link at each end. The bridge encapsulates
     * the functionality for both CDC and SerDes and is a Consumer
     * object similiar to a NetworkLink.
     *
     * If a bridge was enabled we connect the NI and Routers to
     * bridge before connecting the link. Example, if a source
     * bridge is enabled, we would connect:
     * Router--->NetworkBridge--->GarnetIntLink---->Router
     */
    if (garnet_link->dstBridgeEn) {
        DPRINTF(RubyNetwork, "Enable destination bridge for %s\n",
            garnet_link->name());
        NetworkBridge *n_bridge = garnet_link->dstNetBridge;
        m_routers[dest]->addInPort(dst_inport_dirn, n_bridge,
                                   garnet_link->dstCredBridge);
        m_networkbridges.push_back(n_bridge);
    } else {
        m_routers[dest]->addInPort(dst_inport_dirn, net_link, credit_link);
    }

    if (garnet_link->srcBridgeEn) {
        DPRINTF(RubyNetwork, "Enable source bridge for %s\n",
            garnet_link->name());
        NetworkBridge *n_bridge = garnet_link->srcNetBridge;
        m_routers[src]->
            addOutPort(src_outport_dirn, n_bridge,
                       routing_table_entry,
                       link->m_weight, garnet_link->srcCredBridge,
                       m_routers[dest]->get_vc_per_vnet());
        m_networkbridges.push_back(n_bridge);
    } else {
        m_routers[src]->addOutPort(src_outport_dirn, net_link,
                        routing_table_entry,
                        link->m_weight, credit_link,
                        m_routers[dest]->get_vc_per_vnet());
    }
}

// Total routers in the network
int
GarnetNetwork::getNumRouters()
{
    return m_routers.size();
}

// Get ID of router connected to a NI.
int
GarnetNetwork::get_router_id(int global_ni, int vnet)
{
    NodeID local_ni = getLocalNodeID(global_ni);

    return m_nis[local_ni]->get_router_id(vnet);
}

void
GarnetNetwork::regStats()
{
    Network::regStats();

    m_collective_rounds_completed
        .name(name() + ".collective_rounds_completed");
    m_collective_deliveries
        .name(name() + ".collective_deliveries");
    m_collective_source_flits
        .name(name() + ".collective_source_flits");
    m_collective_router_flits
        .name(name() + ".collective_router_flits");
    m_collective_reduce_merges
        .name(name() + ".collective_reduce_merges");
    m_collective_completion_ticks
        .name(name() + ".collective_completion_ticks");
    m_average_collective_completion_ticks
        .name(name() + ".average_collective_completion_ticks");
    m_average_collective_completion_ticks =
        m_collective_completion_ticks / m_collective_rounds_completed;
    m_collective_tensor_requests_completed
        .name(name() + ".collective_tensor_requests_completed");
    m_collective_tensor_lanes_delivered
        .name(name() + ".collective_tensor_lanes_delivered");
    m_collective_tensor_p50_completion_ticks
        .name(name() + ".collective_tensor_p50_completion_ticks");
    m_collective_tensor_p95_completion_ticks
        .name(name() + ".collective_tensor_p95_completion_ticks");
    m_collective_tensor_p99_completion_ticks
        .name(name() + ".collective_tensor_p99_completion_ticks");
    m_collective_credit_stalls
        .name(name() + ".collective_credit_stalls");
    m_collective_tensor_peak_lanes
        .name(name() + ".collective_tensor_peak_lanes");
    m_collective_tensor_measurement_ticks
        .name(name() + ".collective_tensor_measurement_ticks");
    m_multicast_logical_requests
        .name(name() + ".multicast_logical_requests");
    m_multicast_physical_packets
        .name(name() + ".multicast_physical_packets");
    m_multicast_internal_link_flits
        .name(name() + ".multicast_internal_link_flits");
    m_multicast_replication_events
        .name(name() + ".multicast_replication_events");
    m_multicast_credit_stalls
        .name(name() + ".multicast_credit_stalls");
    m_multicast_min_completion_ticks
        .name(name() + ".multicast_min_completion_ticks");
    m_multicast_max_completion_ticks
        .name(name() + ".multicast_max_completion_ticks");
    m_multicast_measurement_ticks
        .name(name() + ".multicast_measurement_ticks");
    m_multicast_measured_requests
        .name(name() + ".multicast_measured_requests");
    m_multicast_measured_completion_ticks
        .name(name() + ".multicast_measured_completion_ticks");
    m_multicast_p95_completion_ticks
        .name(name() + ".multicast_p95_completion_ticks");
    m_multicast_measured_internal_link_flits
        .name(name() + ".multicast_measured_internal_link_flits");
    m_multicast_destination_latency_ticks
        .name(name() + ".multicast_destination_latency_ticks");
    m_multicast_average_destination_latency_ticks
        .name(name() + ".multicast_average_destination_latency_ticks");
    m_multicast_average_destination_latency_ticks =
        m_multicast_destination_latency_ticks / m_collective_deliveries;
    m_multicast_completed_per_cycle
        .name(name() + ".multicast_completed_per_cycle");
    m_multicast_completed_per_cycle =
        m_multicast_measured_requests / m_multicast_measurement_ticks *
        clockPeriod();

    // Packets
    m_packets_received
        .init(m_virtual_networks)
        .name(name() + ".packets_received")
        .flags(statistics::pdf | statistics::total | statistics::nozero |
            statistics::oneline)
        ;

    m_packets_injected
        .init(m_virtual_networks)
        .name(name() + ".packets_injected")
        .flags(statistics::pdf | statistics::total | statistics::nozero |
            statistics::oneline)
        ;

    m_packet_network_latency
        .init(m_virtual_networks)
        .name(name() + ".packet_network_latency")
        .flags(statistics::oneline)
        ;

    m_packet_queueing_latency
        .init(m_virtual_networks)
        .name(name() + ".packet_queueing_latency")
        .flags(statistics::oneline)
        ;
    m_packet_latency_histogram
        .init(16384)
        .name(name() + ".packet_latency_histogram");

    for (int i = 0; i < m_virtual_networks; i++) {
        m_packets_received.subname(i, csprintf("vnet-%i", i));
        m_packets_injected.subname(i, csprintf("vnet-%i", i));
        m_packet_network_latency.subname(i, csprintf("vnet-%i", i));
        m_packet_queueing_latency.subname(i, csprintf("vnet-%i", i));
    }

    m_avg_packet_vnet_latency
        .name(name() + ".average_packet_vnet_latency")
        .flags(statistics::oneline);
    m_avg_packet_vnet_latency =
        m_packet_network_latency / m_packets_received;

    m_avg_packet_vqueue_latency
        .name(name() + ".average_packet_vqueue_latency")
        .flags(statistics::oneline);
    m_avg_packet_vqueue_latency =
        m_packet_queueing_latency / m_packets_received;

    m_avg_packet_network_latency
        .name(name() + ".average_packet_network_latency");
    m_avg_packet_network_latency =
        sum(m_packet_network_latency) / sum(m_packets_received);

    m_avg_packet_queueing_latency
        .name(name() + ".average_packet_queueing_latency");
    m_avg_packet_queueing_latency
        = sum(m_packet_queueing_latency) / sum(m_packets_received);

    m_avg_packet_latency
        .name(name() + ".average_packet_latency");
    m_avg_packet_latency
        = m_avg_packet_network_latency + m_avg_packet_queueing_latency;

    // Flits
    m_flits_received
        .init(m_virtual_networks)
        .name(name() + ".flits_received")
        .flags(statistics::pdf | statistics::total | statistics::nozero |
            statistics::oneline)
        ;

    m_flits_injected
        .init(m_virtual_networks)
        .name(name() + ".flits_injected")
        .flags(statistics::pdf | statistics::total | statistics::nozero |
            statistics::oneline)
        ;

    m_flit_network_latency
        .init(m_virtual_networks)
        .name(name() + ".flit_network_latency")
        .flags(statistics::oneline)
        ;

    m_flit_queueing_latency
        .init(m_virtual_networks)
        .name(name() + ".flit_queueing_latency")
        .flags(statistics::oneline)
        ;

    for (int i = 0; i < m_virtual_networks; i++) {
        m_flits_received.subname(i, csprintf("vnet-%i", i));
        m_flits_injected.subname(i, csprintf("vnet-%i", i));
        m_flit_network_latency.subname(i, csprintf("vnet-%i", i));
        m_flit_queueing_latency.subname(i, csprintf("vnet-%i", i));
    }

    m_avg_flit_vnet_latency
        .name(name() + ".average_flit_vnet_latency")
        .flags(statistics::oneline);
    m_avg_flit_vnet_latency = m_flit_network_latency / m_flits_received;

    m_avg_flit_vqueue_latency
        .name(name() + ".average_flit_vqueue_latency")
        .flags(statistics::oneline);
    m_avg_flit_vqueue_latency =
        m_flit_queueing_latency / m_flits_received;

    m_avg_flit_network_latency
        .name(name() + ".average_flit_network_latency");
    m_avg_flit_network_latency =
        sum(m_flit_network_latency) / sum(m_flits_received);

    m_avg_flit_queueing_latency
        .name(name() + ".average_flit_queueing_latency");
    m_avg_flit_queueing_latency =
        sum(m_flit_queueing_latency) / sum(m_flits_received);

    m_avg_flit_latency
        .name(name() + ".average_flit_latency");
    m_avg_flit_latency =
        m_avg_flit_network_latency + m_avg_flit_queueing_latency;


    // Hops
    m_avg_hops.name(name() + ".average_hops");
    m_avg_hops = m_total_hops / sum(m_flits_received);

    // Links
    m_total_ext_in_link_utilization
        .name(name() + ".ext_in_link_utilization");
    m_total_ext_out_link_utilization
        .name(name() + ".ext_out_link_utilization");
    m_total_int_link_utilization
        .name(name() + ".int_link_utilization");
    m_ordinary_internal_link_flits
        .name(name() + ".ordinary_internal_link_flits");
    m_express_internal_link_flits
        .name(name() + ".express_internal_link_flits");
    m_router_traversals
        .name(name() + ".router_traversals");
    m_physical_wire_flit_distance
        .name(name() + ".physical_wire_flit_distance");
    m_physical_hops_skipped
        .name(name() + ".physical_hops_skipped");
    m_average_link_utilization
        .name(name() + ".avg_link_utilization");
    int maximum_link_id = -1;
    for (const auto *link : m_networklinks)
        maximum_link_id = std::max(maximum_link_id, link->get_id());
    m_internal_link_activity
        .init(maximum_link_id + 1)
        .name(name() + ".internal_link_activity")
        .flags(statistics::total | statistics::nozero);
    for (int id = 0; id <= maximum_link_id; ++id)
        m_internal_link_activity.subname(id, csprintf("link-%d", id));
    m_average_vc_load
        .init(m_virtual_networks * m_max_vcs_per_vnet)
        .name(name() + ".avg_vc_load")
        .flags(statistics::pdf | statistics::total | statistics::nozero |
            statistics::oneline)
        ;

    // Traffic distribution
    for (int source = 0; source < m_routers.size(); ++source) {
        m_data_traffic_distribution.push_back(
            std::vector<statistics::Scalar *>());
        m_ctrl_traffic_distribution.push_back(
            std::vector<statistics::Scalar *>());

        for (int dest = 0; dest < m_routers.size(); ++dest) {
            statistics::Scalar *data_packets = new statistics::Scalar();
            statistics::Scalar *ctrl_packets = new statistics::Scalar();

            data_packets->name(name() + ".data_traffic_distribution." + "n" +
                    std::to_string(source) + "." + "n" + std::to_string(dest));
            m_data_traffic_distribution[source].push_back(data_packets);

            ctrl_packets->name(name() + ".ctrl_traffic_distribution." + "n" +
                    std::to_string(source) + "." + "n" + std::to_string(dest));
            m_ctrl_traffic_distribution[source].push_back(ctrl_packets);
        }
    }
}

void
GarnetNetwork::collateStats()
{
    RubySystem *rs = params().ruby_system;
    double time_delta = double(curCycle() - rs->getStartCycle());

    for (int i = 0; i < m_networklinks.size(); i++) {
        link_type type = m_networklinks[i]->getType();
        int activity = m_networklinks[i]->getLinkUtilization();

        if (type == EXT_IN_)
            m_total_ext_in_link_utilization += activity;
        else if (type == EXT_OUT_)
            m_total_ext_out_link_utilization += activity;
        else if (type == INT_) {
            m_total_int_link_utilization += activity;
            m_internal_link_activity[m_networklinks[i]->get_id()] += activity;
            m_router_traversals += activity;
            const auto bypass =
                std::find(m_bypass_link_ids.begin(), m_bypass_link_ids.end(),
                          m_networklinks[i]->get_id());
            if (bypass != m_bypass_link_ids.end()) {
                const int index = bypass - m_bypass_link_ids.begin();
                const int span = m_bypass_link_spans[index];
                m_express_internal_link_flits += activity;
                m_physical_wire_flit_distance += activity * span;
                m_physical_hops_skipped += activity * (span - 1);
            } else {
                m_ordinary_internal_link_flits += activity;
                m_physical_wire_flit_distance += activity;
            }
        }

        m_average_link_utilization +=
            (double(activity) / time_delta);

        std::vector<unsigned int> vc_load = m_networklinks[i]->getVcLoad();
        for (int j = 0; j < vc_load.size(); j++) {
            m_average_vc_load[j] += ((double)vc_load[j] / time_delta);
        }
    }

    // Ask the routers to collate their statistics
    for (int i = 0; i < m_routers.size(); i++) {
        m_routers[i]->collateStats();
    }
}

void
GarnetNetwork::resetStats()
{
    for (int i = 0; i < m_routers.size(); i++) {
        m_routers[i]->resetStats();
    }
    for (int i = 0; i < m_networklinks.size(); i++) {
        m_networklinks[i]->resetStats();
    }
    for (int i = 0; i < m_creditlinks.size(); i++) {
        m_creditlinks[i]->resetStats();
    }
}

void
GarnetNetwork::print(std::ostream& out) const
{
    out << "[GarnetNetwork]";
}

void
GarnetNetwork::update_traffic_distribution(RouteInfo route)
{
    int src_node = route.src_router;
    int dest_node = route.dest_router;
    int vnet = route.vnet;

    if (m_vnet_type[vnet] == DATA_VNET_)
        (*m_data_traffic_distribution[src_node][dest_node])++;
    else
        (*m_ctrl_traffic_distribution[src_node][dest_node])++;
}

bool
GarnetNetwork::functionalRead(Packet *pkt, WriteMask &mask)
{
    bool read = false;
    for (unsigned int i = 0; i < m_routers.size(); i++) {
        if (m_routers[i]->functionalRead(pkt, mask))
            read = true;
    }

    for (unsigned int i = 0; i < m_nis.size(); ++i) {
        if (m_nis[i]->functionalRead(pkt, mask))
            read = true;
    }

    for (unsigned int i = 0; i < m_networklinks.size(); ++i) {
        if (m_networklinks[i]->functionalRead(pkt, mask))
            read = true;
    }

    for (unsigned int i = 0; i < m_networkbridges.size(); ++i) {
        if (m_networkbridges[i]->functionalRead(pkt, mask))
            read = true;
    }

    return read;
}

uint32_t
GarnetNetwork::functionalWrite(Packet *pkt)
{
    uint32_t num_functional_writes = 0;

    for (unsigned int i = 0; i < m_routers.size(); i++) {
        num_functional_writes += m_routers[i]->functionalWrite(pkt);
    }

    for (unsigned int i = 0; i < m_nis.size(); ++i) {
        num_functional_writes += m_nis[i]->functionalWrite(pkt);
    }

    for (unsigned int i = 0; i < m_networklinks.size(); ++i) {
        num_functional_writes += m_networklinks[i]->functionalWrite(pkt);
    }

    return num_functional_writes;
}

} // namespace garnet
} // namespace ruby
} // namespace gem5
