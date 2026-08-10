/*
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


#include "mem/ruby/network/garnet/RoutingUnit.hh"

#include "base/cast.hh"
#include "base/compiler.hh"
#include "debug/RubyNetwork.hh"
#include "mem/ruby/network/garnet/InputUnit.hh"
#include "mem/ruby/network/garnet/OutputUnit.hh"
#include "mem/ruby/network/garnet/Router.hh"
#include "mem/ruby/slicc_interface/Message.hh"

namespace gem5
{

namespace ruby
{

namespace garnet
{

RoutingUnit::RoutingUnit(Router *router)
{
    m_router = router;
    m_routing_table.clear();
    m_weight_table.clear();
}

void
RoutingUnit::addRoute(std::vector<NetDest>& routing_table_entry)
{
    if (routing_table_entry.size() > m_routing_table.size()) {
        m_routing_table.resize(routing_table_entry.size());
    }
    for (int v = 0; v < routing_table_entry.size(); v++) {
        m_routing_table[v].push_back(routing_table_entry[v]);
    }
}

void
RoutingUnit::addWeight(int link_weight)
{
    m_weight_table.push_back(link_weight);
}

bool
RoutingUnit::supportsVnet(int vnet, std::vector<int> sVnets)
{
    // If all vnets are supported, return true
    if (sVnets.size() == 0) {
        return true;
    }

    // Find the vnet in the vector, return true
    if (std::find(sVnets.begin(), sVnets.end(), vnet) != sVnets.end()) {
        return true;
    }

    // Not supported vnet
    return false;
}

/*
 * This is the default routing algorithm in garnet.
 * The routing table is populated during topology creation.
 * Routes can be biased via weight assignments in the topology file.
 * Correct weight assignments are critical to provide deadlock avoidance.
 */
int
RoutingUnit::lookupRoutingTable(int vnet, NetDest msg_destination)
{
    // First find all possible output link candidates
    // For ordered vnet, just choose the first
    // (to make sure different packets don't choose different routes)
    // For unordered vnet, randomly choose any of the links
    // To have a strict ordering between links, they should be given
    // different weights in the topology file

    int output_link = -1;
    int min_weight = INFINITE_;
    std::vector<int> output_link_candidates;
    int num_candidates = 0;

    // Identify the minimum weight among the candidate output links
    for (int link = 0; link < m_routing_table[vnet].size(); link++) {
        if (msg_destination.intersectionIsNotEmpty(
            m_routing_table[vnet][link])) {

        if (m_weight_table[link] <= min_weight)
            min_weight = m_weight_table[link];
        }
    }

    // Collect all candidate output links with this minimum weight
    for (int link = 0; link < m_routing_table[vnet].size(); link++) {
        if (msg_destination.intersectionIsNotEmpty(
            m_routing_table[vnet][link])) {

            if (m_weight_table[link] == min_weight) {
                num_candidates++;
                output_link_candidates.push_back(link);
            }
        }
    }

    if (output_link_candidates.size() == 0) {
        fatal("Fatal Error:: No Route exists from this Router.");
        exit(0);
    }

    // Randomly select any candidate output link
    int candidate = 0;
    if (!(m_router->get_net_ptr())->isVNetOrdered(vnet))
        candidate = rand() % num_candidates;

    output_link = output_link_candidates.at(candidate);
    return output_link;
}


void
RoutingUnit::addInDirection(PortDirection inport_dirn, int inport_idx)
{
    m_inports_dirn2idx[inport_dirn] = inport_idx;
    m_inports_idx2dirn[inport_idx]  = inport_dirn;
}

void
RoutingUnit::addOutDirection(PortDirection outport_dirn, int outport_idx)
{
    m_outports_dirn2idx[outport_dirn] = outport_idx;
    m_outports_idx2dirn[outport_idx]  = outport_dirn;
}

// outportCompute() is called by the InputUnit
// It calls the routing table by default.
// A template for adaptive topology-specific routing algorithm
// implementations using port directions rather than a static routing
// table is provided here.

int
RoutingUnit::outportCompute(RouteInfo route, int inport,
                            PortDirection inport_dirn)
{
    int outport = -1;

    if (route.dest_router == m_router->get_id()) {

        // Multiple NIs may be connected to this router,
        // all with output port direction = "Local"
        // Get exact outport id from table
        outport = lookupRoutingTable(route.vnet, route.net_dest);
        return outport;
    }

    // Routing Algorithm set in GarnetNetwork.py
    // Can be over-ridden from command line using --routing-algorithm = 1
    RoutingAlgorithm routing_algorithm =
        (RoutingAlgorithm) m_router->get_net_ptr()->getRoutingAlgorithm();

    switch (routing_algorithm) {
        case TABLE_:  outport =
            lookupRoutingTable(route.vnet, route.net_dest); break;
        case XY_:     outport =
            outportComputeXY(route, inport, inport_dirn); break;
        // any custom algorithm
        case CUSTOM_: outport =
            outportComputeCustom(route, inport, inport_dirn); break;
        default: outport =
            lookupRoutingTable(route.vnet, route.net_dest); break;
    }

    assert(outport != -1);
    return outport;
}

// XY routing implemented using port directions
// Only for reference purpose in a Mesh
// By default Garnet uses the routing table
int
RoutingUnit::outportComputeXY(RouteInfo route,
                              int inport,
                              PortDirection inport_dirn)
{
    PortDirection outport_dirn = "Unknown";

    [[maybe_unused]] int num_rows = m_router->get_net_ptr()->getNumRows();
    int num_cols = m_router->get_net_ptr()->getNumCols();
    assert(num_rows > 0 && num_cols > 0);

    int my_id = m_router->get_id();
    int my_x = my_id % num_cols;
    int my_y = my_id / num_cols;

    int dest_id = route.dest_router;
    int dest_x = dest_id % num_cols;
    int dest_y = dest_id / num_cols;

    int x_hops = abs(dest_x - my_x);
    int y_hops = abs(dest_y - my_y);

    bool x_dirn = (dest_x >= my_x);
    bool y_dirn = (dest_y >= my_y);

    // already checked that in outportCompute() function
    assert(!(x_hops == 0 && y_hops == 0));

    if (x_hops > 0) {
        if (x_dirn) {
            assert(inport_dirn == "Local" || inport_dirn == "West");
            outport_dirn = "East";
        } else {
            assert(inport_dirn == "Local" || inport_dirn == "East");
            outport_dirn = "West";
        }
    } else if (y_hops > 0) {
        if (y_dirn) {
            // "Local" or "South" or "West" or "East"
            assert(inport_dirn != "North");
            outport_dirn = "North";
        } else {
            // "Local" or "North" or "West" or "East"
            assert(inport_dirn != "South");
            outport_dirn = "South";
        }
    } else {
        // x_hops == 0 and y_hops == 0
        // this is not possible
        // already checked that in outportCompute() function
        panic("x_hops == y_hops == 0");
    }

    return m_outports_dirn2idx[outport_dirn];
}

// Template for implementing custom routing algorithm
// using port directions. (Example adaptive)
int
RoutingUnit::outportComputeCustom(RouteInfo route,
                                 int inport,
                                 PortDirection inport_dirn)
{
    const int routers = m_router->get_net_ptr()->getNumRouters();
    const auto& first_hops = m_router->get_net_ptr()->getBypassFirstHops();
    fatal_if(first_hops.size() != routers * routers,
             "Custom bypass routing requires %d first-hop entries; got %d",
             routers * routers, (int)first_hops.size());
    fatal_if(route.src_router < 0 || route.src_router >= routers ||
             route.dest_router < 0 || route.dest_router >= routers,
             "Invalid bypass route %d -> %d", route.src_router,
             route.dest_router);

    if (m_router->get_id() == route.src_router) {
        const PortDirection& direction =
            first_hops[route.src_router * routers + route.dest_router];
        if (direction != "XY") {
            const auto outport = m_outports_dirn2idx.find(direction);
            fatal_if(outport == m_outports_dirn2idx.end(),
                     "Bypass route %d -> %d requests missing port %s",
                     route.src_router, route.dest_router, direction.c_str());

            // Express links reduce hop count, but a static oracle can funnel
            // many destinations onto one source shortcut.  For unordered
            // traffic, compare source-port pressure and fall back to the
            // deterministic XY route when its first output has more free
            // VCs.  The choice is made only at injection, so every selected
            // suffix remains deterministic XY and the audited channel order
            // is unchanged.  Ordered vnets retain the static route to avoid
            // packet reordering.
            GarnetNetwork *network = m_router->get_net_ptr();
            if (network->bypassAdaptiveRouting() &&
                !network->isVNetOrdered(route.vnet)) {
                const int xy_outport =
                    outportComputeXY(route, inport, "Local");
                const unsigned max_packet_flits =
                    network->bypassAdaptiveMaxPacketFlits();
                if (max_packet_flits &&
                    route.packet_flits > max_packet_flits)
                    return xy_outport;
                const int express_free = m_router->getOutputUnit(
                    outport->second)->count_free_vcs(route.vnet);
                const int xy_free = m_router->getOutputUnit(
                    xy_outport)->count_free_vcs(route.vnet);
                const int vcs_per_vnet = m_router->getOutputUnit(
                    outport->second)->getVcsPerVnet();

                // The shortcut's reverse credit path can cheaply carry a
                // coarse congestion bit for the landing Router's next
                // output.  Consult that one-express-hop lookahead before
                // committing to a path that would immediately join a busy
                // hotspot convergence port.
                const auto& first_hop_destinations =
                    network->getBypassFirstHopDestinations();
                const int landing = first_hop_destinations[
                    route.src_router * routers + route.dest_router];
                fatal_if(landing < 0 || landing >= routers,
                         "Missing bypass landing for route %d -> %d",
                         route.src_router, route.dest_router);
                const int columns = network->getNumCols();
                const int landing_x = landing % columns;
                const int landing_y = landing / columns;
                const int destination_x = route.dest_router % columns;
                const int destination_y = route.dest_router / columns;
                PortDirection lookahead_direction = "Local";
                if (landing_x < destination_x) {
                    lookahead_direction = "East";
                } else if (landing_x > destination_x) {
                    lookahead_direction = "West";
                } else if (landing_y < destination_y) {
                    lookahead_direction = "North";
                } else if (landing_y > destination_y) {
                    lookahead_direction = "South";
                }
                Router *landing_router = network->getRouter(landing);
                int lookahead_outport = -1;
                for (int port = 0;
                     port < landing_router->get_num_outports(); ++port) {
                    if (landing_router->getOutportDirection(port) ==
                        lookahead_direction) {
                        lookahead_outport = port;
                        break;
                    }
                }
                fatal_if(lookahead_outport < 0,
                         "Bypass landing %d has no %s output for %d -> %d",
                         landing, lookahead_direction.c_str(),
                         route.src_router, route.dest_router);
                const int lookahead_free = landing_router->getOutputUnit(
                    lookahead_outport)->count_free_vcs(route.vnet);
                const int lookahead_low_watermark = vcs_per_vnet;
                if (lookahead_free < lookahead_low_watermark)
                    return xy_outport;

                // Small free-VC differences are too noisy at light load.
                // Reserve the shortcut for a decisive source-pressure
                // advantage so occasional allocator timing does not create a
                // longer tail through an otherwise uncongested landing router.
                if (express_free <= xy_free + 1)
                    return xy_outport;
            }
            return outport->second;
        }
    }
    // The offline oracle proves the source-express/XY channel ordering.  An
    // express input direction is intentionally not one of XY's traditional
    // compass inports, so use XY only for its deterministic coordinate step.
    return outportComputeXY(route, inport, "Local");
}

} // namespace garnet
} // namespace ruby
} // namespace gem5
