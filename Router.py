from random import randrange
import setup
import json
import socket
import select
import sys
import time
import copy

BUFFER_SIZE = 1024
HOST = "127.0.0.1"

# Length Constants
MIN_LENGTH_PACKET = 4  # Require Command, Version, and Router-Id fields with at least one RIP entry.
MAX_LENGTH_PACKET = 28  # Require Command, Version, and Router-Id fields with up to 25 RIP entries.

ENTRY_INDEX = 3  # "Initial" index of entries
MAX_METRIC = 16
PERIODIC_UPDATE = 5
PACKET_TIMEOUT = 30
GARBAGE_COLLECTION = 20


class Router:
    def __init__(self, data, sockets):
        self.router_id = data[0]  # Id of this router.
        self.input_ports = data[1]
        self.output_ports = data[2]
        self.valid_packet = False  # Keeps track of whether a received response packet contains correct data.
        self.error_msg = ""  # If a valid is not packet this message is displayed.
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
                if len(packet[entry]) > 0:
                    if packet[entry]['metric'] < 1 or packet[entry]['metric'] > 16:
                        self.valid_packet = False
                        self.error_msg = "The metric for a RIP entry is invalid"
                        break
                    else:
                        self.valid_packet = True
                        self.error_msg = ""
                else:
                    self.valid_packet = True
                    self.error_msg = ""
                    break

    def create_response_packet(self, destination_router_id):
        """Creates a RIP response packet based on the specifications."""
        self.response_packet = dict()

        self.response_packet['command'] = 2
        self.response_packet['version'] = 2
        self.response_packet['router_id'] = self.router_id

        # Consider setup when initial routing table is empty.
        if len(self.routing_table) == 0:
            self.response_packet["entry1"] = dict()  # empty
            return self.response_packet

        entry_number = 1
        for entry, data in self.routing_table.items():
            # Need to make a new copy of data, otherwise following operations overwrite routing table.
            data_to_send = copy.deepcopy(data)
            # Routes learnt from neighbor included in updates sent to that neighbor.
            # "Split horizon with poisoned reverse" is used.
            if data['next_router_id'] == destination_router_id:
                # Sets their metrics to "infinity"/unreachable as required by "Split horizon with poisoned reverse"
                data_to_send['metric'] = MAX_METRIC
            if data['destination_router_id'] != destination_router_id:
                entry_access = "entry" + str(entry_number)
                self.response_packet[entry_access] = data_to_send
                entry_number += 1

        return self.response_packet

    def read_response_packet(self, packet):
        """Reads a RIP response packet and updates RIP entries in routing table. If no RIP entry exists then
        a function is called to add that RIP entry to the routing table.
        """
        self.validate_response_packet(packet)

        if self.valid_packet:
            time_read = time.time()
            # Consider setup when initial routing table is empty.
            if len(packet["entry1"]) == 0:
                self.add_neighbour(packet)  # empty
                return

            distance_to_next_hop = 0
            found_neighbour = False
            # Retrieves the metric for the distance between this router and the router which it received packet from.
            # This metric will be added to further metric calculations.
            for entry_next_hop, data_next_hop in self.routing_table.items():
                if data_next_hop['destination_router_id'] == packet['router_id']:
                    distance_to_next_hop = int(data_next_hop['metric'])
                    found_neighbour = True
                    break
            # Received a packet from a router that is a neighbour to this router,
            # which hasn't been added to the routing table of this router.
            # Add router to this routing table, and receive metric.
            if not found_neighbour:
                distance_to_next_hop = int(self.add_neighbour(packet))

            trigger_update = False  # If a route becomes unreachable (metric = 16), an update needs to be triggered.
            to_add = []  # new routes to add.
            for entry_number in range(1, len(packet) - ENTRY_INDEX):
                found = False  # Keeps track of whether entry for destination router already exists.
                entry_access = "entry" + str(entry_number)
                for entry, data in self.routing_table.items():
                    if data['destination_router_id'] == packet[entry_access]['destination_router_id']:
                        # If the new distance is smaller than the existing value, adopt the new route.
                        if (int(packet[entry_access]['metric']) + distance_to_next_hop) < int(data['metric']):
                            # Update routing table
                            if (int(packet[entry_access]['metric']) + distance_to_next_hop) > 16:
                                self.routing_table[entry]['metric'] = MAX_METRIC
                                trigger_update = True
                            else:
                                self.routing_table[entry]['metric'] = int(packet[entry_access]['metric']) + \
                                                                      distance_to_next_hop
                            self.routing_table[entry]['next_router_id'] = packet['router_id']
                            self.routing_table[entry]['flag'] = True
                            self.routing_table[entry]['time'] = (time_read, None)
                            # If the router from which the existing route came, then use the new metric
                            # even if it is larger than the old one.
                        elif data['next_router_id'] == packet['router_id']:
                            self.routing_table[entry]['flag'] = True
                            if (int(packet[entry_access]['metric']) + distance_to_next_hop) > 16:
                                self.routing_table[entry]['metric'] = MAX_METRIC
                                trigger_update = True
                            else:
                                self.routing_table[entry]['metric'] = int(packet[entry_access]['metric']) + \
                                                                      int(distance_to_next_hop)
                        #update timer as recieved packet from router
                        self.routing_table[entry]['time']
                        # Entry found for destination router so set to true
                        # (data['destination_router_id'] == packet[entry_access]['router_id'])
                        found = True
                # If no entry for destination is found then a new one is created.
                if not found:
                    to_add.append((packet, entry_access, distance_to_next_hop, time))
            # If the metric of an entry has been set to 16 (unreachable) then this router needs to notify other routers.
            if trigger_update:
                self.trigger_update()

            current_time = time.time()
            for new_route in to_add:
                self.add_routing_table_entry(new_route[0], new_route[1], new_route[2])
            #checking whether packet has expired if it has set time to null then if time = null when reciving packet destroy entry
            for entry, data in self.routing_table.items():
                if (entry["time"][0] >= (time + PACKET_TIMEOUT)):
                    self.routing_table[entry]["time"] = (None, current_time)
                    self.routing_table[entry]['metric'] = MAX_METRIC
                elif (entry["time"][1] >= (time + GARBAGE_COLLECTION)):
                    del self.routing_table[entry]
                else:
                    self.routing_table[entry]["time"] = (current_time, None)

            return
        else:
            print(self.error_msg)
            print("Discarding packet...")
            return

    def add_routing_table_entry(self, packet, entry_access, distance_to_next_hop, time):
        """
        Adds an entry to routing table for the router.

        Routing Table Entry:

        - destination_router-id, the router id of the destination.
        - metric, cost of sending datagram from router to destination.
        - next_router_id, the router id of the next router along the path to the destination,
        empty string if directly connected (in our setup).
        - flag, indicates whether the route has changed recently. (True or False)
        """
        destination_router = packet[entry_access]['destination_router_id']
        next_router = packet['router_id']
        distance = int(packet[entry_access]['metric']) + distance_to_next_hop

        entry = len(self.routing_table)
        self.routing_table[entry] = {'destination_router_id': destination_router, 'metric': int(distance),
                                     'next_router_id': next_router, 'flag': True, 'time': time}

    def add_neighbour(self, packet):
        '''During initial setup if this router receives an empty entry from another,
        router this means that it is a neighbour (i.e. directly connect). The directly connect neighbour is then
        added to the routing table of this router.'''

        for port in self.output_ports:
            metric = port[1]
            destination = port[2]

            entry_number = len(self.routing_table)
            if packet['router_id'] == destination:
                insert_entry = True
                new_entry = {'destination_router_id': destination, 'metric': int(metric),
                             'next_router_id': "", 'flag': True, 'time': time.time()}
                for entry, data in self.routing_table.items():
                    if data == new_entry:
                        insert_entry = False
                        break
                if insert_entry:
                    self.routing_table[entry_number] = new_entry
                    return metric
        return 0

    def trigger_update(self):
        for port in self.output_ports:
            port_number = port[0]
            destination_router_id = port[2]
            readable, writeable, in_error = select.select(self.sockets, self.sockets, [])
            if len(writeable) > 0:  # At least one socket is free to send a response packet
                writeable_socket = writeable[0]  # doesn't matter what socket is used to send, so select first one.
                response_packet = self.create_response_packet(destination_router_id)
                response_packet_bytes = json.dumps(response_packet).encode('utf-8')
                writeable_socket.sendto(response_packet_bytes, (HOST, int(port_number)))

    def __str__(self):
        """Returns the formatted string represent of the Router's routing table"""
        string = "===========================================================\n" \
                 "Routing Table: \n" \
                 " \n" \
                 "Destination  |  Metric  |  Next-Hop  |  Flag  |  Timeout(s)\n"
        for entry, data in self.routing_table.items():
            string += "    {0}            {1}           {2}           {3}      {4}".format(
                data['destination_router_id'], data['metric'], data['next_router_id'], data['flag'], data['time'])
            string += "\n"
        string += "===========================================================\n"
        return string


def main():
    config = setup.get_config_file()
    data_from_config = setup.get_router_data(config)
    input_ports = data_from_config[1]
    sockets = []

    # Create datagram sockets for each port.
    # Bind sockets to each port.
    for port in input_ports:
        try:
            port_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
            port_socket.bind((HOST, int(port)))
            sockets.append(port_socket)
        except OSError:
            print("Port already in use. Terminating...")
            sys.exit()

    router = Router(data_from_config, sockets)
    print(router)  # Print initial routing table of router (empty).

    while True:

        time.sleep(PERIODIC_UPDATE * randrange(8, 12, 1) / 10)

        readable, writeable, in_error = select.select(router.sockets, router.sockets, [])

        # Send
        for port in router.output_ports:
            port_number = port[0]
            destination_router_id = port[2]
            if len(writeable) > 0:  # At least one socket is free to send a response packet
                writeable_socket = writeable[0]  # doesn't matter what socket is used to send, so select first one.
                response_packet = router.create_response_packet(destination_router_id)
                response_packet_bytes = json.dumps(response_packet).encode('utf-8')
                writeable_socket.sendto(response_packet_bytes, (HOST, int(port_number)))

        # Receive
        if len(readable) > 0:
            for readable_socket in readable:
                try:
                    temporary_storage = readable_socket.recvfrom(BUFFER_SIZE)[0]
                    response_packet = json.loads(temporary_storage.decode('utf-8'))
                    router.read_response_packet(response_packet)
                    # Print the routing table to command line to see the changes that occur when
                    # receiving a response packet.
                    print(router)
                except ConnectionResetError:
                    # Prevents the router from crashing when neighbour is not yet online.
                    print("")


main()
