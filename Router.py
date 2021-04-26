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
        self.routing_table = []
        self.response_packet = dict()
        self.sockets = sockets
        self.trigger = False

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

    def check_timers(self, current_time):
        delete = []
        # checking whether packet has expired if it has set time to null then if time = null when receiving packet
        # destroy entry
        for data in self.routing_table:
            if (data['time'][0] is not None) and (current_time > (data['time'][0] + PACKET_TIMEOUT)) \
                    or (data['metric'] >= MAX_METRIC and (data['garbage'] is not True)):
                data['time'] = (None, current_time)
                data['metric'] = MAX_METRIC
                data['garbage'] = True
                self.trigger = True
                if data['next_router_id'] != "":
                    delete.append(data)
            if (data['time'][0] is None) and (data['time'][1] is not None) and (
                    current_time > (data['time'][1] + GARBAGE_COLLECTION)):
                delete.append(data)
                # Updating timers from received neighbour.
        for data_to_delete in delete:
            self.routing_table.remove(data_to_delete)

        self.update_neighbour()

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
        for data in self.routing_table:
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
            # Consider setup when initial routing table is empty.
            if len(self.routing_table) == 0 or len(packet['entry1']) == 0:
                self.add_neighbour(packet)  # empty
                return

            distance_to_next_hop = 0
            found_neighbour = False
            # Retrieves the metric for the distance between this router and the router which it received packet from.
            # This metric will be added to further metric calculations.
            for data_next_hop in self.routing_table:
                if data_next_hop['destination_router_id'] == packet['router_id']:
                    distance_to_next_hop = int(data_next_hop['metric'])
                    found_neighbour = True
                    break
            # Received a packet from a router that is a neighbour to this router,
            # which hasn't been added to the routing table of this router.
            # Add router to this routing table, and receive metric.
            if not found_neighbour:
                distance_to_next_hop = int(self.add_neighbour(packet))

            to_add = []  # new routes to add.
            for entry_number in range(1, len(packet) - 2):
                found = False  # Keeps track of whether entry for destination router already exists.
                entry_access = "entry" + str(entry_number)
                for data in self.routing_table:
                    if data['destination_router_id'] == packet[entry_access]['destination_router_id']:
                        metric = int(packet[entry_access]['metric']) + distance_to_next_hop
                        # If the new distance is smaller than the existing value, adopt the new route.
                        if metric < int(data['metric']):
                            # Update routing table
                            if metric > MAX_METRIC:
                                data['metric'] = MAX_METRIC
                                self.trigger = True
                            else:
                                data['metric'] = metric
                            data['next_router_id'] = packet['router_id']
                            data['flag'] = True
                            # If the router from which the existing route came, then use the new metric
                            # even if it is larger than the old one.
                        elif data['next_router_id'] == packet['router_id']:
                            data['flag'] = True
                            if metric > MAX_METRIC:
                                data['metric'] = MAX_METRIC
                                self.trigger = True
                            else:
                                data['metric'] = metric
                        # Entry found for destination router so set to true
                        # (data['destination_router_id'] == packet[entry_access]['router_id'])
                        found = True
                # If no entry for destination is found then a new one is created.
                if not found:
                    if metric < MAX_METRIC:
                        print('Adding new entry')
                        to_add.append((packet, entry_access, distance_to_next_hop))
            current_time = time.time()
            for data in self.routing_table:
                if (packet['router_id'] == data['next_router_id']) or \
                        (packet['router_id'] == data['destination_router_id']):
                    data['time'] = (current_time, None)
            # If the metric of an entry has been set to 16 (unreachable) then this router needs to notify other routers.

            for new_route in to_add:
                self.add_routing_table_entry(new_route[0], new_route[1], new_route[2])
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
        current_time = time.time()
        destination_router = packet[entry_access]['destination_router_id']
        next_router = packet['router_id']
        distance = int(packet[entry_access]['metric']) + distance_to_next_hop

        print('Adding router entry.')
        self.routing_table.append({'destination_router_id': destination_router, 'metric': distance,
                                   'next_router_id': next_router, 'flag': True, 'time': (current_time, None),
                                   'garbage': False})

    def add_neighbour(self, packet):
        """During initial setup if this router receives an empty entry from another,
        router this means that it is a neighbour (i.e. directly connect). The directly connect neighbour is then
        added to the routing table of this router."""
        for port in self.output_ports:
            metric = port[1]
            destination = port[2]

            if packet['router_id'] == destination:
                insert_entry = True
                new_entry = {'destination_router_id': destination, 'metric': int(metric),
                             'next_router_id': "", 'flag': True, 'time': (time.time(), None), 'garbage': False}
                for data in self.routing_table:
                    if data['destination_router_id'] == new_entry['destination_router_id']:
                        insert_entry = False
                        break
                if insert_entry:
                    self.routing_table.append(new_entry)
                    return metric
        return 0

    def update_neighbour(self):
        """updates neighbour"""
        current_time = time.time()
        for port in self.output_ports:
            metric = int(port[1])
            destination = port[2]
            for data in self.routing_table:
                if destination == data['destination_router_id']:
                    if (data['time'][0] is not None) and (current_time > (data['time'][0] + PACKET_TIMEOUT)):
                        data['metric'] = metric
                        data['next_router_id'] = ""

    def trigger_update(self, writeable):
        for port in self.output_ports:
            port_number = port[0]
            destination_router_id = port[2]
            # At least one socket is free to send a response packet
            writeable_socket = writeable[0]  # doesn't matter what socket is used to send, so select first one.
            response_packet = self.create_response_packet(destination_router_id)
            response_packet_bytes = json.dumps(response_packet).encode('utf-8')
            writeable_socket.sendto(response_packet_bytes, (HOST, int(port_number)))
        self.trigger = False

    def __str__(self):
        """Returns the formatted string represent of the Router's routing table"""
        string = "=====================================================================================\n" \
                 "Routing Table: \n" \
                 " \n" \
                 "Destination  |  Metric  |  Next-Hop  |  Flag  |  Timeout(s)  |  Garbage Collection(s)\n"
        for data in self.routing_table:
            if data['time'][0] is None:
                timeout = 0.00
            else:
                timeout = time.time() - data['time'][0]
            if data['time'][1] is None:
                garbage = 0.00
            else:
                garbage = time.time() - data['time'][1]
            string += "{0:<14} {1:<12} {2:<12} {3:<8} {4:6.2f} {5:18.2f}".format(
                data['destination_router_id'], data['metric'], data['next_router_id'], data['flag'], timeout, garbage)
            string += "\n"
        string += "=====================================================================================\n"
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
        router.check_timers(time.time())

        readable, writeable, in_error = select.select(router.sockets, router.sockets, [])

        if router.trigger and (len(writeable) > 0):
            router.trigger_update(writeable)

        time.sleep(PERIODIC_UPDATE * (randrange(8, 12, 1) / 10))
        # Receive
        if len(readable) > 0:
            for readable_socket in readable:
                try:
                    temporary_storage = readable_socket.recvfrom(BUFFER_SIZE)[0]
                    response_packet = json.loads(temporary_storage.decode('utf-8'))
                    router.read_response_packet(response_packet)
                    # Print the routing table to command line to see the changes that occur when
                    # receiving a response packet.
                except ConnectionResetError:
                    # Prevents the router from crashing when neighbour is not yet online.
                    print("")

        # Send
        if len(writeable) > 0:
            print(router)
            router.trigger_update(writeable)


main()
