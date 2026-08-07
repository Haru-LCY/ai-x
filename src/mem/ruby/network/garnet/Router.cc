/*
 * Copyright (c) 2020 Advanced Micro Devices, Inc.
 * Copyright (c) 2020 Inria
 * Copyright (c) 2016 Georgia Institute of Technology
 * Copyright (c) 2008 Princeton University
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


#include "mem/ruby/network/garnet/Router.hh"

#include "debug/RubyNetwork.hh"
#include "mem/ruby/network/garnet/CreditLink.hh"
#include "mem/ruby/network/garnet/GarnetNetwork.hh"
#include "mem/ruby/network/garnet/InputUnit.hh"
#include "mem/ruby/network/garnet/NetworkLink.hh"
#include "mem/ruby/network/garnet/OutputUnit.hh"

namespace gem5
{

namespace ruby
{

namespace garnet
{

Router::Router(const Params &p)
  : BasicRouter(p), Consumer(this), m_latency(p.latency),
    m_virtual_networks(p.virt_nets), m_vc_per_vnet(p.vcs_per_vnet),
    m_num_vcs(m_virtual_networks * m_vc_per_vnet), m_bit_width(p.width),
    m_network_ptr(nullptr), m_collective_root(p.collective_root),
    m_collective_enabled(p.collective_enabled),
    m_collective_multicast(p.collective_multicast),
    m_collective_parent_outport(p.collective_parent_outport),
    m_collective_child_inports(p.collective_child_inports),
    m_collective_expected_fanin(p.collective_expected_fanin),
    m_collective_accum(0), m_collective_count(0), m_collective_id(-1),
    m_collective_active(false),
    routingUnit(this), switchAllocator(this),
    crossbarSwitch(this)
{
    m_input_unit.clear();
    m_output_unit.clear();
}

void
Router::init()
{
    BasicRouter::init();

    switchAllocator.init();
    crossbarSwitch.init();

    if (!m_collective_enabled)
        return;

    if (m_collective_multicast)
        return;

    fatal_if(m_collective_root && !m_collective_parent_outport.empty(),
             "Collective root router %d has parent direction %s", m_id,
             m_collective_parent_outport.c_str());
    fatal_if(!m_collective_root && m_collective_parent_outport.empty(),
             "Non-root router %d has no collective parent", m_id);
    fatal_if(m_collective_expected_fanin !=
                 m_collective_child_inports.size() + 1,
             "Router %d collective fan-in %u does not match %u children", m_id,
             m_collective_expected_fanin,
             (unsigned)m_collective_child_inports.size());

    DPRINTF(RubyNetwork,
            "Lab4 tree: router=%d root=%d parent=%s fanin=%u children=%u\n",
            m_id, m_collective_root, m_collective_parent_outport.c_str(),
            m_collective_expected_fanin,
            (unsigned)m_collective_child_inports.size());
}

void
Router::wakeup()
{
    DPRINTF(RubyNetwork, "Router %d woke up\n", m_id);
    assert(clockEdge() == curTick());

    // check for incoming flits
    for (int inport = 0; inport < m_input_unit.size(); inport++) {
        m_input_unit[inport]->wakeup();
    }

    // check for incoming credits
    // Note: the credit update is happening before SA
    // buffer turnaround time =
    //     credit traversal (1-cycle) + SA (1-cycle) + Link Traversal (1-cycle)
    // if we want the credit update to take place after SA, this loop should
    // be moved after the SA request
    for (int outport = 0; outport < m_output_unit.size(); outport++) {
        m_output_unit[outport]->wakeup();
    }

    // Switch Allocation
    switchAllocator.wakeup();

    // Switch Traversal
    crossbarSwitch.wakeup();
}

void
Router::addInPort(PortDirection inport_dirn,
                  NetworkLink *in_link, CreditLink *credit_link)
{
    fatal_if(in_link->bitWidth != m_bit_width, "Widths of link %s(%d)does"
            " not match that of Router%d(%d). Consider inserting SerDes "
            "Units.", in_link->name(), in_link->bitWidth, m_id, m_bit_width);

    int port_num = m_input_unit.size();
    InputUnit *input_unit = new InputUnit(port_num, inport_dirn, this);

    input_unit->set_in_link(in_link);
    input_unit->set_credit_link(credit_link);
    in_link->setLinkConsumer(this);
    in_link->setVcsPerVnet(get_vc_per_vnet());
    credit_link->setSourceQueue(input_unit->getCreditQueue(), this);
    credit_link->setVcsPerVnet(get_vc_per_vnet());

    m_input_unit.push_back(std::shared_ptr<InputUnit>(input_unit));

    routingUnit.addInDirection(inport_dirn, port_num);
}

void
Router::addOutPort(PortDirection outport_dirn,
                   NetworkLink *out_link,
                   std::vector<NetDest>& routing_table_entry, int link_weight,
                   CreditLink *credit_link, uint32_t consumerVcs)
{
    fatal_if(out_link->bitWidth != m_bit_width, "Widths of units do not match."
            " Consider inserting SerDes Units");

    int port_num = m_output_unit.size();
    OutputUnit *output_unit = new OutputUnit(port_num, outport_dirn, this,
                                             consumerVcs);

    output_unit->set_out_link(out_link);
    output_unit->set_credit_link(credit_link);
    credit_link->setLinkConsumer(this);
    credit_link->setVcsPerVnet(consumerVcs);
    out_link->setSourceQueue(output_unit->getOutQueue(), this);
    out_link->setVcsPerVnet(consumerVcs);

    m_output_unit.push_back(std::shared_ptr<OutputUnit>(output_unit));

    routingUnit.addRoute(routing_table_entry);
    routingUnit.addWeight(link_weight);
    routingUnit.addOutDirection(outport_dirn, port_num);
}

PortDirection
Router::getOutportDirection(int outport)
{
    return m_output_unit[outport]->get_direction();
}

PortDirection
Router::getInportDirection(int inport)
{
    return m_input_unit[inport]->get_direction();
}

int
Router::route_compute(RouteInfo route, int inport, PortDirection inport_dirn)
{
    return routingUnit.outportCompute(route, inport, inport_dirn);
}

void
Router::grant_switch(int inport, flit *t_flit)
{
    crossbarSwitch.update_sw_winner(inport, t_flit);
}

void
Router::schedule_wakeup(Cycles time)
{
    // wake up after time cycles
    scheduleEvent(time);
}

int
Router::collectiveOutport(const std::string& direction) const
{
    for (int i = 0; i < m_output_unit.size(); ++i) {
        if (m_output_unit[i]->get_direction() == direction)
            return i;
    }
    return -1;
}

int
Router::collectiveChildId(const std::string& child_inport) const
{
    const int cols = m_network_ptr->getNumCols();
    const int x = m_id % cols;
    const int y = m_id / cols;
    // The input direction names the direction from this router toward the
    // child: a child east of us sends west and arrives on our East input.
    if (child_inport == "East")
        return y * cols + (x + 1);
    if (child_inport == "West")
        return y * cols + (x - 1);
    if (child_inport == "North")
        return (y + 1) * cols + x;
    if (child_inport == "South")
        return (y - 1) * cols + x;
    fatal("Invalid Lab4 child input direction %s at Router %d",
          child_inport, m_id);
}

void
Router::sendCollectiveFlit(int64_t value, CollectiveOp op, int dest_router,
                            flit *template_flit)
{
    const int cols = m_network_ptr->getNumCols();
    const int out_x = dest_router % cols;
    const int out_y = dest_router / cols;
    const int x = m_id % cols;
    const int y = m_id / cols;
    std::string direction = "Local";
    if (out_x > x) direction = "East";
    else if (out_x < x) direction = "West";
    else if (out_y > y) direction = "North";
    else if (out_y < y) direction = "South";

    const int outport = collectiveOutport(direction);
    fatal_if(outport < 0, "Router %d has no Lab4 output %s", m_id,
             direction);
    OutputUnit *output = m_output_unit[outport].get();
    const int vnet = template_flit->get_vnet();
    const int outvc = output->select_free_vc(vnet);
    fatal_if(outvc < 0, "Router %d has no free VC for Lab4 collective", m_id);

    RouteInfo route = template_flit->get_route();
    route.src_ni = m_network_ptr->getNumRouters() + m_id;
    route.src_router = m_id;
    route.dest_ni = m_network_ptr->getNumRouters() + dest_router;
    route.dest_router = dest_router;
    route.net_dest.clear();
    route.net_dest.add(MachineID(MachineType_Directory, dest_router));
    route.hops_traversed = -1;

    flit *out_flit = new flit(m_network_ptr->getNextPacketID(), 0, outvc,
        vnet, route, 1, template_flit->get_msg_ptr(), template_flit->msgSize,
        m_bit_width, curTick());
    out_flit->set_value(value);
    out_flit->set_collective_id(template_flit->get_collective_id());
    out_flit->set_collective_op(op);
    m_network_ptr->recordCollectiveRouterFlit();
    output->decrement_credit(outvc);
    output->insert_flit(out_flit);
    DPRINTF(RubyNetwork,
            "Lab4 collective send round=%d router=%d dest_router=%d op=%d "
            "value=%ld\
",
            template_flit->get_collective_id(), m_id, dest_router,
            static_cast<int>(op), (long)value);
}

void
Router::handleCollectiveFlit(flit *t_flit, int inport)
{
    fatal_if(!m_collective_enabled,
             "Lab4 flit reached Router %d without collective metadata", m_id);
    fatal_if(t_flit->get_size() != 1 || t_flit->get_type() != HEAD_TAIL_,
             "Lab4 scalar collective at Router %d must be a single "
             "HEAD_TAIL flit", m_id);
    const CollectiveOp op = t_flit->get_collective_op();
    if (op == CollectiveOp::Multicast || op == CollectiveOp::Broadcast) {
        fatal_if(op == CollectiveOp::Multicast && !m_collective_multicast,
                 "Router %d received multicast in all-reduce mode", m_id);
        fatal_if(op == CollectiveOp::Broadcast && m_collective_multicast,
                 "Router %d received broadcast in multicast mode", m_id);

        // Broadcast and multicast share the same tree forwarding operation:
        // deliver one local copy and replicate one copy to each child.
        sendCollectiveFlit(t_flit->get_value(), op, m_id, t_flit);
        for (const auto& child_in : m_collective_child_inports)
            sendCollectiveFlit(t_flit->get_value(), op,
                               collectiveChildId(child_in), t_flit);
        getInputUnit(inport)->increment_credit(t_flit->get_vc(), true,
                                                curTick());
        delete t_flit;
        return;
    }
    fatal_if(op != CollectiveOp::Reduce,
             "Router %d received invalid Lab4 collective operation", m_id);
    if (!m_collective_active) {
        m_collective_active = true;
        m_collective_accum = 0;
        m_collective_count = 0;
        m_collective_id = t_flit->get_collective_id();
    } else {
        fatal_if(t_flit->get_collective_id() != m_collective_id,
                 "Router %d received mixed Lab4 collective ids", m_id);
    }

    m_collective_accum += t_flit->get_value();
    ++m_collective_count;
    getInputUnit(inport)->increment_credit(t_flit->get_vc(), true, curTick());

    if (m_collective_count == m_collective_expected_fanin) {
        const int64_t sum = m_collective_accum;
        if (m_collective_root) {
            // Include the root's local NI and every child in the broadcast.
            sendCollectiveFlit(sum, CollectiveOp::Broadcast, m_id, t_flit);
            for (const auto& child_in : m_collective_child_inports)
                sendCollectiveFlit(sum, CollectiveOp::Broadcast,
                                    collectiveChildId(child_in), t_flit);
        } else {
            const int cols = m_network_ptr->getNumCols();
            const int x = m_id % cols;
            const int y = m_id / cols;
            int parent = m_id;
            if (m_collective_parent_outport == "East") parent = y * cols + x + 1;
            else if (m_collective_parent_outport == "West") parent = y * cols + x - 1;
            else if (m_collective_parent_outport == "North") parent = (y + 1) * cols + x;
            else if (m_collective_parent_outport == "South") parent = (y - 1) * cols + x;
            sendCollectiveFlit(sum, CollectiveOp::Reduce, parent, t_flit);
        }
        m_collective_active = false;
        m_collective_count = 0;
        m_collective_accum = 0;
        m_collective_id = -1;
    }
    delete t_flit;
}

std::string
Router::getPortDirectionName(PortDirection direction)
{
    // PortDirection is actually a string
    // If not, then this function should add a switch
    // statement to convert direction to a string
    // that can be printed out
    return direction;
}

void
Router::regStats()
{
    BasicRouter::regStats();

    m_buffer_reads
        .name(name() + ".buffer_reads")
        .flags(statistics::nozero)
    ;

    m_buffer_writes
        .name(name() + ".buffer_writes")
        .flags(statistics::nozero)
    ;

    m_crossbar_activity
        .name(name() + ".crossbar_activity")
        .flags(statistics::nozero)
    ;

    m_sw_input_arbiter_activity
        .name(name() + ".sw_input_arbiter_activity")
        .flags(statistics::nozero)
    ;

    m_sw_output_arbiter_activity
        .name(name() + ".sw_output_arbiter_activity")
        .flags(statistics::nozero)
    ;
}

void
Router::collateStats()
{
    for (int j = 0; j < m_virtual_networks; j++) {
        for (int i = 0; i < m_input_unit.size(); i++) {
            m_buffer_reads += m_input_unit[i]->get_buf_read_activity(j);
            m_buffer_writes += m_input_unit[i]->get_buf_write_activity(j);
        }
    }

    m_sw_input_arbiter_activity = switchAllocator.get_input_arbiter_activity();
    m_sw_output_arbiter_activity =
        switchAllocator.get_output_arbiter_activity();
    m_crossbar_activity = crossbarSwitch.get_crossbar_activity();
}

void
Router::resetStats()
{
    for (int i = 0; i < m_input_unit.size(); i++) {
            m_input_unit[i]->resetStats();
    }

    crossbarSwitch.resetStats();
    switchAllocator.resetStats();
}

void
Router::printFaultVector(std::ostream& out)
{
    int temperature_celcius = BASELINE_TEMPERATURE_CELCIUS;
    int num_fault_types = m_network_ptr->fault_model->number_of_fault_types;
    float fault_vector[num_fault_types];
    get_fault_vector(temperature_celcius, fault_vector);
    out << "Router-" << m_id << " fault vector: " << std::endl;
    for (int fault_type_index = 0; fault_type_index < num_fault_types;
         fault_type_index++) {
        out << " - probability of (";
        out <<
        m_network_ptr->fault_model->fault_type_to_string(fault_type_index);
        out << ") = ";
        out << fault_vector[fault_type_index] << std::endl;
    }
}

void
Router::printAggregateFaultProbability(std::ostream& out)
{
    int temperature_celcius = BASELINE_TEMPERATURE_CELCIUS;
    float aggregate_fault_prob;
    get_aggregate_fault_probability(temperature_celcius,
                                    &aggregate_fault_prob);
    out << "Router-" << m_id << " fault probability: ";
    out << aggregate_fault_prob << std::endl;
}

bool
Router::functionalRead(Packet *pkt, WriteMask &mask)
{
    bool read = false;
    if (crossbarSwitch.functionalRead(pkt, mask))
        read = true;

    for (uint32_t i = 0; i < m_input_unit.size(); i++) {
        if (m_input_unit[i]->functionalRead(pkt, mask))
            read = true;
    }

    for (uint32_t i = 0; i < m_output_unit.size(); i++) {
        if (m_output_unit[i]->functionalRead(pkt, mask))
            read = true;
    }

    return read;
}

uint32_t
Router::functionalWrite(Packet *pkt)
{
    uint32_t num_functional_writes = 0;
    num_functional_writes += crossbarSwitch.functionalWrite(pkt);

    for (uint32_t i = 0; i < m_input_unit.size(); i++) {
        num_functional_writes += m_input_unit[i]->functionalWrite(pkt);
    }

    for (uint32_t i = 0; i < m_output_unit.size(); i++) {
        num_functional_writes += m_output_unit[i]->functionalWrite(pkt);
    }

    return num_functional_writes;
}

} // namespace garnet
} // namespace ruby
} // namespace gem5
