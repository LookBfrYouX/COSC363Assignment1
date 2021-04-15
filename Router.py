import setup
import json

# Length Constants
MIN_LENGTH_PACKET = 4  # Require Command, Version, and Router-Id fields with at least one RIP entry.
MAX_LENGTH_PACKET = 28  # Require Command, Version, and Router-Id fields with up to 25 RIP entries.

ENTRY_INDEX = 3  # "Initial" index of entries


class Router:
    def __init__(self, data):
        self.router_id = data[0]
        self.input_ports = data[1]
        self.output_ports = data[2]
        self.valid_packet = False
        self.error_msg = ""
        self.routing_table = dict()
        self.response_packet = dict()
        self.destination_router_id = ""

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

    def populate_routing_table(self, setup_packets):
        """
        Sets up the initial routing table for the router.
        These are the direct connections to the router and will have a metric of 1.

        Routing Table Entry:

        - destination_router-id, the router id of the destination.
        - metric, cost of sending datagram from router to destination.
        - next_router_id, the router id of the next router along the path to the destination,
        empty string if directly connected (in our setup).
        - flag, indicates whether the route has changed recently. (True or False)
        """
        for packet in setup_packets:
            router_id = packet['router_id']
            entry_number = len(self.routing_table)
            self.routing_table[entry_number] = {'destination_router-id': router_id, 'metric': 1,
                                                'next_router_id': "", 'flag': True}

    def create_setup_response_packet(self):
        """Create a RIP response packet that will be used for setup."""
        self.response_packet = dict()

        self.response_packet['command'] = 2
        self.response_packet['version'] = 2
        self.response_packet['router_id'] = self.router_id
        self.response_packet['entry1'] = {self.router_id, 0}  # Metric is zero because router is connected to its self.

        return self.response_packet

    def create_response_packet(self):
        """Creates a RIP response packet based on the specifications."""
        self.response_packet = dict()

        self.response_packet['command'] = 2
        self.response_packet['version'] = 2
        self.response_packet['router_id'] = self.router_id

        entry_number = 1
        for entry in self.routing_table:
            # Routes learnt from neighbor included in updates sent to that neighbor.
            # "Split horizon with poisoned reverse" is used.
            # TODO this will probably have to be changed, because self.destination_router_id is not updated,
            #  maybe pass in destination_router_id.
            if entry['next_router_id'] == self.destination_router_id:
                # Sets their metrics to "infinity"/unreachable as required by "Split horizon with poisoned reverse"
                entry['metric'] = 16
            entry_access = "entry" + str(entry_number)
            self.response_packet[entry_access] = entry
            entry_number += 1

        return self.response_packet

    def read_response_packet(self, packet):
        """Reads a RIP response packet and calls function to add/update RIP entries in routing table."""
        self.validate_response_packet(packet)
        distance = 1
        # Routing update arrives from a neighbor G', add the cost associated with the network that is shared with G'.
        # (This should be the network over which the update arrived.) Call the resulting distance D'.
        # Compare the resulting distances with the current routing table entries. If the new distance D' for N is
        # smaller than the existing value D, adopt the new route.That is, change the table entry for N to have metric D'
        # and router G'.If G' is the router from which the existing route came, i.e., G' = G, then use the new metric
        # even if it is larger than the old one.

        if self.valid_packet:
            entry_number = 1
            for entry in self.routing_table:
                entry_access = "entry" + str(entry_number)
                if entry['destination_router_id'] == packet[entry_access]['router_id']:
                    break
                # if entry id and metric < packet id and metric + 1, else if entry-id =
                entry_number += 1
            # Update routing table
            return
        else:
            print(self.error_msg)
            print("Discarding packet...")
            return

    def update_routing_table(self):
        return self.routing_table


config = setup.get_config_file()
data_from_config = setup.get_router_data(config)
router1 = Router(data_from_config)
