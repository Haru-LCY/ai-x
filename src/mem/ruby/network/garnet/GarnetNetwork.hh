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


#ifndef __MEM_RUBY_NETWORK_GARNET_0_GARNETNETWORK_HH__
#define __MEM_RUBY_NETWORK_GARNET_0_GARNETNETWORK_HH__

#include <iostream>
#include <set>
#include <utility>
#include <vector>

#include "mem/ruby/network/Network.hh"
#include "mem/ruby/network/fault_model/FaultModel.hh"
#include "mem/ruby/network/garnet/CommonTypes.hh"
#include "mem/ruby/network/garnet/flit.hh"
#include "params/GarnetNetwork.hh"

namespace gem5
{

namespace ruby
{

class FaultModel;
class NetDest;

namespace garnet
{

class NetworkInterface;
class Router;
class NetworkLink;
class NetworkBridge;
class CreditLink;

class GarnetNetwork : public Network
{
  public:
    typedef GarnetNetworkParams Params;
    GarnetNetwork(const Params &p);
    ~GarnetNetwork() = default;

    void init();

    const char *garnetVersion = "3.0";

    // Configuration (set externally)

    // for 2D topology
    int getNumRows() const { return m_num_rows; }
    int getNumCols() { return m_num_cols; }

    // for network
    uint32_t getNiFlitSize() const { return m_ni_flit_size; }
    uint32_t getBuffersPerDataVC() { return m_buffers_per_data_vc; }
    uint32_t getBuffersPerCtrlVC() { return m_buffers_per_ctrl_vc; }
    int getRoutingAlgorithm() const { return m_routing_algorithm; }
    Router *getRouter(int id) const
    {
        assert(id >= 0 && id < m_routers.size());
        return m_routers[id];
    }
    const std::vector<std::string>& getBypassFirstHops() const
    {
        return m_bypass_first_hops;
    }
    const std::vector<int>& getBypassFirstHopDestinations() const
    {
        return m_bypass_first_hop_destinations;
    }
    bool bypassAdaptiveRouting() const { return m_bypass_adaptive_routing; }
    unsigned bypassAdaptiveMaxPacketFlits() const
    {
        return m_bypass_adaptive_max_packet_flits;
    }
    bool collectiveMode() const { return m_collective_mode; }
    bool collectiveMulticast() const { return m_collective_multicast; }
    bool collectiveTensor() const { return m_collective_tensor; }
    bool collectiveTraffic(int vnet, int source_router) const
    {
        return m_collective_mode && vnet == m_collective_vnet &&
               (!m_collective_multicast ||
                source_router == m_multicast_source);
    }
    bool treeMulticast() const { return m_multicast_mode == "tree_multicast"; }
    bool naiveMulticast() const { return m_multicast_mode == "naive_unicast"; }
    int multicastSource() const { return m_multicast_source; }
    bool multicastDestination(int router_id) const;
    bool multicastDestination(uint64_t destinations, int router_id) const;
    bool multicastChildNeeded(uint64_t destinations, int router_id,
                              int child_id) const;
    uint64_t multicastDestinationMask() const
    {
        return m_multicast_destination_mask;
    }
    int multicastDestinationCount() const { return m_multicast_destination_count; }
    int multicastPacketFlits() const { return m_multicast_packet_flits; }
    int collectivePacketLaneStart() const
    {
        return m_collective_packet_lane_start;
    }
    void setCollectivePacketLaneStart(int start)
    {
        fatal_if(start < 0,
                 "Collective packet lane start must be non-negative");
        m_collective_packet_lane_start = start;
    }
    void setMulticastPacketFlits(int flits)
    {
        fatal_if(flits < 1, "Multicast packet must contain at least one flit");
        m_multicast_packet_flits = flits;
    }
    bool canInjectCollectiveRound(int collective_id) const;
    int nextNaiveMulticastRound();

    bool isFaultModelEnabled() const { return m_enable_fault_model; }
    FaultModel* fault_model;


    // Internal configuration
    bool isVNetOrdered(int vnet) const { return m_ordered[vnet]; }
    VNET_type
    get_vnet_type(int vnet)
    {
        return m_vnet_type[vnet];
    }
    int getNumRouters();
    int get_router_id(int ni, int vnet);


    // Methods used by Topology to setup the network
    void makeExtOutLink(SwitchID src, NodeID dest, BasicLink* link,
                     std::vector<NetDest>& routing_table_entry);
    void makeExtInLink(NodeID src, SwitchID dest, BasicLink* link,
                    std::vector<NetDest>& routing_table_entry);
    void makeInternalLink(SwitchID src, SwitchID dest, BasicLink* link,
                          std::vector<NetDest>& routing_table_entry,
                          PortDirection src_outport_dirn,
                          PortDirection dest_inport_dirn);

    bool functionalRead(Packet *pkt, WriteMask &mask);
    //! Function for performing a functional write. The return value
    //! indicates the number of messages that were written.
    uint32_t functionalWrite(Packet *pkt);

    // Stats
    void collateStats();
    void regStats();
    void resetStats();
    void print(std::ostream& out) const;

    // increment counters
    void increment_injected_packets(int vnet) { m_packets_injected[vnet]++; }
    void increment_received_packets(int vnet) { m_packets_received[vnet]++; }

    int syntheticPacketFlits() const { return m_synthetic_packet_flits; }

    void
    increment_packet_network_latency(Tick latency, int vnet)
    {
        m_packet_network_latency[vnet] += latency;
    }

    void
    increment_packet_queueing_latency(Tick latency, int vnet)
    {
        m_packet_queueing_latency[vnet] += latency;
    }

    void samplePacketLatency(Cycles latency)
    {
        m_packet_latency_histogram.sample(latency);
    }

    void increment_injected_flits(int vnet) { m_flits_injected[vnet]++; }
    void increment_received_flits(int vnet) { m_flits_received[vnet]++; }

    void
    increment_flit_network_latency(Tick latency, int vnet)
    {
        m_flit_network_latency[vnet] += latency;
    }

    void
    increment_flit_queueing_latency(Tick latency, int vnet)
    {
        m_flit_queueing_latency[vnet] += latency;
    }

    void
    increment_total_hops(int hops)
    {
        m_total_hops += hops;
    }

    void update_traffic_distribution(RouteInfo route);
    int getNextPacketID() { return m_next_packet_id++; }
    void recordCollectiveDelivery(int collective_id, int dest_router,
                                  int lane = -1);
    void setCollectiveRoundTensorLanes(int collective_id, int lanes);
    void assertNoResidualCollectiveState();
    void beginCollectiveRound(int collective_id);
    void recordMulticastLocalDelivery(int collective_id);
    void recordCollectiveInjection(int collective_id, int source_flits = 1);
    void recordCollectiveRouterFlit() { ++m_collective_router_flits; }
    void recordCollectiveReduceMerge() { ++m_collective_reduce_merges; }
    void recordCollectiveCreditStall() { ++m_collective_credit_stalls; }
    void recordCollectiveWrongValue()
    {
        ++m_collective_wrong_value_deliveries;
    }
    void recordCollectiveOutvcStall() { ++m_collective_outvc_stalls; }
    void recordCollectiveInternalLinkFlit(CollectiveOp op);
    void recordMulticastInternalLinkFlit(int collective_id);
    void recordMulticastCreditStall() { ++m_multicast_credit_stalls; }
    void recordMulticastReplication(int fanout)
    {
        if (fanout > 1)
            ++m_multicast_replication_events;
    }

  protected:
    // Configuration
    int m_num_rows;
    int m_num_cols;
    uint32_t m_ni_flit_size;
    uint32_t m_max_vcs_per_vnet;
    uint32_t m_buffers_per_ctrl_vc;
    uint32_t m_buffers_per_data_vc;
    int m_routing_algorithm;
    std::vector<std::string> m_bypass_first_hops;
    std::vector<int> m_bypass_first_hop_destinations;
    std::vector<int> m_bypass_link_ids;
    std::vector<int> m_bypass_link_spans;
    bool m_bypass_adaptive_routing;
    unsigned m_bypass_adaptive_max_packet_flits;
    int m_synthetic_packet_flits;
    bool m_collective_mode;
    bool m_collective_multicast;
    bool m_collective_tensor;
    int m_collective_rounds;
    std::string m_multicast_mode;
    int m_multicast_source;
    int m_multicast_packet_flits;
    int m_collective_packet_lane_start = 0;
    int m_collective_vnet;
    std::string m_multicast_workload;
    int m_multicast_max_outstanding;
    int m_multicast_warmup_rounds;
    int m_multicast_measurement_rounds;
    int m_multicast_cooldown_rounds;
    std::vector<bool> m_multicast_destinations;
    uint64_t m_multicast_destination_mask = 0;
    int m_multicast_destination_count = 0;
    bool m_enable_fault_model;

    // Statistical variables
    statistics::Vector m_packets_received;
    statistics::Vector m_packets_injected;
    statistics::Vector m_packet_network_latency;
    statistics::Vector m_packet_queueing_latency;
    statistics::SparseHistogram m_packet_latency_histogram;

    statistics::Formula m_avg_packet_vnet_latency;
    statistics::Formula m_avg_packet_vqueue_latency;
    statistics::Formula m_avg_packet_network_latency;
    statistics::Formula m_avg_packet_queueing_latency;
    statistics::Formula m_avg_packet_latency;

    statistics::Vector m_flits_received;
    statistics::Vector m_flits_injected;
    statistics::Vector m_flit_network_latency;
    statistics::Vector m_flit_queueing_latency;

    statistics::Formula m_avg_flit_vnet_latency;
    statistics::Formula m_avg_flit_vqueue_latency;
    statistics::Formula m_avg_flit_network_latency;
    statistics::Formula m_avg_flit_queueing_latency;
    statistics::Formula m_avg_flit_latency;

    statistics::Scalar m_total_ext_in_link_utilization;
    statistics::Scalar m_total_ext_out_link_utilization;
    statistics::Scalar m_total_int_link_utilization;
    statistics::Scalar m_ordinary_internal_link_flits;
    statistics::Scalar m_express_internal_link_flits;
    statistics::Scalar m_router_traversals;
    statistics::Scalar m_physical_wire_flit_distance;
    statistics::Scalar m_physical_hops_skipped;
    statistics::Scalar m_average_link_utilization;
    statistics::Vector m_internal_link_activity;
    statistics::Vector m_average_vc_load;

    statistics::Scalar  m_total_hops;
    statistics::Formula m_avg_hops;

    statistics::Scalar m_collective_rounds_completed;
    statistics::Scalar m_collective_deliveries;
    statistics::Scalar m_collective_source_flits;
    statistics::Scalar m_collective_router_flits;
    statistics::Scalar m_collective_reduce_merges;
    statistics::Scalar m_collective_completion_ticks;
    statistics::Formula m_average_collective_completion_ticks;
    statistics::Scalar m_collective_tensor_requests_completed;
    statistics::Scalar m_collective_tensor_lanes_delivered;
    statistics::Scalar m_collective_tensor_p50_completion_ticks;
    statistics::Scalar m_collective_tensor_p95_completion_ticks;
    statistics::Scalar m_collective_tensor_p99_completion_ticks;
    statistics::Scalar m_collective_credit_stalls;
    statistics::Scalar m_collective_duplicate_deliveries;
    statistics::Scalar m_collective_unexpected_deliveries;
    statistics::Scalar m_collective_wrong_lane_deliveries;
    statistics::Scalar m_collective_wrong_value_deliveries;
    statistics::Scalar m_collective_outvc_stalls;
    statistics::Scalar m_collective_reduce_internal_link_flits;
    statistics::Scalar m_collective_broadcast_internal_link_flits;
    statistics::Scalar m_collective_tensor_active_entries;
    statistics::Scalar m_collective_tensor_peak_lanes;
    statistics::Scalar m_collective_tensor_measurement_ticks;
    statistics::Scalar m_multicast_logical_requests;
    statistics::Scalar m_multicast_physical_packets;
    statistics::Scalar m_multicast_internal_link_flits;
    statistics::Scalar m_multicast_replication_events;
    statistics::Scalar m_multicast_credit_stalls;
    statistics::Scalar m_multicast_min_completion_ticks;
    statistics::Scalar m_multicast_max_completion_ticks;
    statistics::Scalar m_multicast_measurement_ticks;
    statistics::Scalar m_multicast_measured_requests;
    statistics::Scalar m_multicast_measured_completion_ticks;
    statistics::Scalar m_multicast_p95_completion_ticks;
    statistics::Scalar m_multicast_measured_internal_link_flits;
    statistics::Scalar m_multicast_destination_latency_ticks;
    statistics::Formula m_multicast_average_destination_latency_ticks;
    statistics::Formula m_multicast_completed_per_cycle;

    std::vector<std::vector<statistics::Scalar *>> m_data_traffic_distribution;
    std::vector<std::vector<statistics::Scalar *>> m_ctrl_traffic_distribution;

  private:
    GarnetNetwork(const GarnetNetwork& obj);
    GarnetNetwork& operator=(const GarnetNetwork& obj);

    std::vector<VNET_type > m_vnet_type;
    std::vector<Router *> m_routers;   // All Routers in Network
    std::vector<NetworkLink *> m_networklinks; // All flit links in the network
    std::vector<NetworkBridge *> m_networkbridges; // All network bridges
    std::vector<CreditLink *> m_creditlinks; // All credit links in the network
    std::vector<NetworkInterface *> m_nis;   // All NI's in Network
    int m_next_packet_id; // static vairable for packet id allocation

    struct CollectiveRoundState
    {
        bool started = false;
        bool completed = false;
        Tick start_tick = 0;
        int delivery_count = 0;
        std::vector<bool> delivered;
        // Lab4 tensor all-reduce: per-(dest, lane) delivery tracking.
        int tensor_lanes = 0;
        int tensor_deliveries = 0;
        std::set<std::pair<int, int>> tensor_delivered;
    };
    std::vector<CollectiveRoundState> m_collective_round_states;
    int m_collective_next_injection_id = 0;
    int m_collective_active_rounds = 0;
    int m_collective_completed_rounds = 0;
    int m_naive_injection_round = 0;
    int m_naive_packets_in_round = 0;
    Tick m_multicast_first_injection_tick = 0;
    Tick m_multicast_last_completion_tick = 0;
    Tick m_multicast_min_latency = MaxTick;
    Tick m_multicast_max_latency = 0;
    Tick m_multicast_measurement_first_injection_tick = 0;
    Tick m_multicast_measurement_last_completion_tick = 0;
    std::vector<Tick> m_multicast_measured_latencies;
    std::vector<Tick> m_tensor_request_latencies;
    Tick m_tensor_first_injection_tick = 0;
    Tick m_tensor_last_completion_tick = 0;

    bool
    isMeasurementRound(int collective_id) const
    {
        return collective_id >= m_multicast_warmup_rounds &&
               collective_id < m_multicast_warmup_rounds +
                                   m_multicast_measurement_rounds;
    }

    // Compatibility cursor: lowest not-yet-completed round.
    int m_collective_delivery_id = 0;
};

inline std::ostream&
operator<<(std::ostream& out, const GarnetNetwork& obj)
{
    obj.print(out);
    out << std::flush;
    return out;
}

} // namespace garnet
} // namespace ruby
} // namespace gem5

#endif //__MEM_RUBY_NETWORK_GARNET_0_GARNETNETWORK_HH__
