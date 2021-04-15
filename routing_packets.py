import json

# Length Constants
MIN_LENGTH_PACKET = 4  # Require Command, Version, and Router-Id fields with at least one RIP entry.
MAX_LENGTH_PACKET = 28  # Require Command, Version, and Router-Id fields with up to 25 RIP entries.

ENTRY_INDEX = 3  # "Initial" index of entries


def create_response_packet():
    """Creates a RIP response packet based on the specifications."""
    response_packet = dict()

    response_packet['command'] = 2
    response_packet['version'] = 2
    # response_packet['router_id'] = this.router_id

    # routes learned from one neighbor in updates
    # sent to that neighbor. "Split horizon with poisoned reverse"
    # includes such routes in updates, but sets their metrics to infinity.

    # entry_number = 1
    # for entry in this.routing_table:
    #     entry_access = "entry" + str(entry_number)
    #     response_packet[entry_access] = entry
    #
    return response_packet


def read_response_packet(packet):
    """Reads a RIP response packet and adds/updates RIP entries in routing table."""
    valid_packet, error_msg = validate_response_packet(packet)
    # if error msg, print and discard packet
    # Routing update arrives from a neighbor G', add the cost associated with the network that is shared with G'.(This
    # should be the network over which the update arrived.) Call the resulting distance D'. Compare the resulting
    # distances with the current routing table entries. If the new distance D' for N is smaller than the existing
    # value D, adopt the new route.That is, change the table entry for N to have metric D' and router G'.If G'
    # is the router from which the existing route came, i.e., G' = G, then use the new metric
    # even if it is larger than the old one.

    if valid_packet:
        # Update routing table
        # if metric is smaller take that
        return
    else:
        print(error_msg)
        return


def validate_response_packet(packet):
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
        valid_packet = False
        error_msg = "The RIP packet does not contain the required fields or contains additional fields."
    elif packet['command'] != 2:
        valid_packet = False
        error_msg = "The command field of the packet is incorrect."
    elif packet['version'] != 2:
        valid_packet = False
        error_msg = "The version field of the packet is incorrect."
    else:
        for i in range(ENTRY_INDEX, len(packet)):
            # TODO add additional checks for content of RIP entry (optional)
            entry = "entry" + str(i - 2)
            if packet[entry]['metric'] < 1 or packet[entry]['metric'] > 16:
                valid_packet = False
                error_msg = "The metric for a RIP entry is invalid"
                break
            else:
                valid_packet = True
                error_msg = ""

    return valid_packet, error_msg


def update_routing_table():
    # Table with an entry for every possible destination in the system. The
    # entry contains the distance D to the destination, and the first router G on the
    # route to that network.

    # - Router-id of destination
    # - Metric represents total cost of getting a datagram from the router to that destination. This metric is the
    # sum of the costs associated with the networks that would be traversed to get to the destination.
    # - Router-id of next router along the path to the destination (i.e., the next hop).
    # If the destination is on one of the directly-connected networks, this item is not needed.
    # - A flag to indicate that information about the route has changed recently.This will be referred to as the
    # "route change flag."
    return


def main():
    packet = {'command': 2, 'version': 2, 'router_id': 100, 'entry1': {'router_id': 10, 'metric': 11}}
    validate_response_packet(packet)

    # Periodically, send a routing update to every neighbor.The update is a set of messages that contain all
    # of the information from the routing table. It contains an entry for each destination, with the
    # distance shown to that destination.


main()
