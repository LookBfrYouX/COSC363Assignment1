# Length Constants
MIN_LENGTH_PACKET = 4  # Require Command, Version, and Router-Id fields with at least one RIP entry.
MAX_LENGTH_PACKET = 28  # Require Command, Version, and Router-Id fields with up to 25 RIP entries.

ENTRY_INDEX = 3  # "Initial" index of entries


class Router:
    def __init__(self, data, sockets):
        self.router_id = data[0]
        self.input_ports = data[1]
        self.output_ports = data[2]
        self.valid_packet = False
        self.error_msg = ""
        self.routing_table = dict()
        self.response_packet = dict()
        self.sockets = sockets

    def validate_response_packet(self, packet):
        """
        Determines if response packet needs to be discarded based on whether fixed
        fields have the right values, the metric is in the correct range etc.

        Packet Format - Common Header:

        Command - Set to 2 for response packet (8 bits)
        Version - Set to 2 for RIP version 2 (8 bits)
        Must Be Zero (Router-Id) - In this case used to store router-id (16 bits)
        RIP Entry - Can have between 1 and 25 RIP entries (160 bits for our case 64 bits as we are ignoring some fields)

        Packet Format - RIP Entry:

        Address family identifier - set to zero because we are using router-ids not addresses (16 bits) IGNORE THIS FIELD
        Must be Zero - set to zero (16 bits) IGNORE THIS FIELD
        Router-id - the id of the destination router (32 bits)
        Must be Zero - set to zero (32 bits) IGNORE THIS FIELD
        Must be Zero - set to zero (32 bits) IGNORE THIS FIELD
        Metric - Value between 1 and 15 inclusive, or 16 (infinity) if destination is unreachable (32 bits)
        """
        if (len(packet) < MIN_LENGTH_PACKET) or (len(packet) > MAX_LENGTH_PACKET):
            self.valid_packet = False
            self.error_msg = "The RIP packet does not contain the required fields or contains additional fields."
        elif packet['command'] != 2:
            self.valid_packet = False
            self.error_msg = "The command field of the packet is incorrect."
        elif packet['version'] != 2:
            self.valid_packet = False
            self.error_msg = "The version field of the packet is incorrect."
        else:
            for i in range(ENTRY_INDEX, len(packet)):
                # TODO add additional checks for content of RIP entry (optional)
                entry = "entry" + str(i - 2)
                if packet[entry]['metric'] < 1 or packet[entry]['metric'] > 16:
                    self.valid_packet = False
                    self.error_msg = "The metric for a RIP entry is invalid"
                    break
                else:
                    self.valid_packet = True
                    self.error_msg = ""

    def create_response_packet(self, destination_router_id):
        """Creates a RIP response packet based on the specifications."""
        self.response_packet = dict()

        self.response_packet['command'] = 2
        self.response_packet['version'] = 2
        self.response_packet['router_id'] = self.router_id

        # Consider setup when initial routing table is empty.
        if len(self.rotuing_table) == 0:
            self.response_packet["entry1"] = dict()  # empty
            return self.response_packet

        entry_number = 1
        for entry, data in self.routing_table.items():
            # Routes learnt from neighbor included in updates sent to that neighbor.
            # "Split horizon with poisoned reverse" is used.
            if data['next_router_id'] == destination_router_id:
                # Sets their metrics to "infinity"/unreachable as required by "Split horizon with poisoned reverse"
                data['metric'] = 16
            entry_access = "entry" + str(entry_number)
            self.response_packet[entry_access] = data
            entry_number += 1

        return self.response_packet

    def read_response_packet(self, packet):
        """Reads a RIP response packet and updates RIP entries in routing table. If no RIP entry exists then
        a function is called to add that RIP entry to the routing table.
        """
        self.validate_response_packet(packet)

        if self.valid_packet:
            # Consider setup when initial routing table is empty.
            if len(packet["entry1"]) == 0:
                self.add_neighbour(packet)  # empty
                return

            distance_to_next_hop = 0
            for entry_next_hop, data_next_hop in self.routing_table.items():
                if data_next_hop['destination_router_id'] == packet['router_id']:
                    distance_to_next_hop = data_next_hop['metric']
                    break
                else:
                    # Received a packet from a router that is a neighbour to this router,
                    # which hasn't been added to the routing table of this router.
                    # Add router to this routing table, and receive metric.
                    distance_to_next_hop = self.add_neighbour(packet)
                    break

            entry_number = 1
            found = False
            for entry, data in self.routing_table.items():
                entry_access = "entry" + str(entry_number)
                if data['destination_router_id'] == packet[entry_access]['router_id']:
                    # If the new distance is smaller than the existing value, adopt the new route.
                    if (packet[entry_access]['metric'] + distance_to_next_hop) < data['metric']:
                        # Update routing table
                        self.routing_table[entry]['metric'] = packet[entry_access]['metric'] + distance_to_next_hop
                        self.routing_table[entry]['next_router_id'] = packet['router_id']
                        self.routing_table[entry]['flag'] = True
                        break
                    # If the router from which the existing route came, then use the new metric
                    # even if it is larger than the old one.
                    elif data['next_router_id'] == packet['router_id']:
                        self.routing_table[entry]['metric'] = packet[entry_access]['metric'] + distance_to_next_hop
                        self.routing_table[entry]['flag'] = True
                    else:
                        break
                entry_number += 1
            if not found:
                self.add_routing_table_entry(packet, entry_access, distance_to_next_hop)
            return
        else:
            print(self.error_msg)
            print("Discarding packet...")
            return

    def add_routing_table_entry(self, packet, entry_access, distance_to_next_hop):
        """
        Adds an entry to routing table for the router.

        Routing Table Entry:

        - destination_router-id, the router id of the destination.
        - metric, cost of sending datagram from router to destination.
        - next_router_id, the router id of the next router along the path to the destination,
        empty string if directly connected (in our setup).
        - flag, indicates whether the route has changed recently. (True or False)
        """
        destination_router = packet[entry_access]['router_id']
        next_router = packet['router_id']
        distance = packet[entry_access]['metric'] + distance_to_next_hop

        entry = len(self.routing_table)
        self.routing_table[entry] = {'destination_router-id': destination_router, 'metric': int(distance),
                                     'next_router_id': next_router, 'flag': True}

    def add_neighbour(self, packet):
        """During initial setup if this router receives an empty entry from another,
        router this means that it is a neighbour (i.e. directly connect). The directly connect neighbour is then
        added to the routing table of this router."""
        for port in self.output_ports:
            metric = port[1]
            destination = port[2]

            entry_number = len(self.routing_table)
            if packet['router_id'] == destination:
                self.routing_table[entry_number] = {'destination_router-id': destination, 'metric': int(metric),
                                                    'next_router_id': "", 'flag': True}
                return metric
        return 0

    def __str__(self):
        """Returns the formatted string represent of the Router's routing table"""
        string = "Routing Table: \n" \
                 " \n" \
                 "Destination Metric Next-Hop \n"
        for entry, data in self.routing_table.items():
            string += "{0} {1} {2} \n"
            string.format(data['destination_router_id'], data['metric'], data['next_router_id'])
        return string
