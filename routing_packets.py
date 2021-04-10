# Length Constants
MIN_LENGTH_PACKET = 5 # Require Command, Version, and Router-Id fields with at least one RIP entry.
MAX_LENGTH_PACKET = 29 # Require Command, Version, and Router-Id fields with up to 25 RIP entries.

# Constants used to index parts of the common header of a RIP packet.
COMMAND = 0
VERSION = 1
SOURCE_ROUTER_ID_B1 = 2
SOURCE_ROUTER_ID_B2 = 3
START_OF_RIP_ENTRIES = 4

# Constants used to index parts of a RIP entry.
DESTINATION_ROUTER_ID_B1 = 0
DESTINATION_ROUTER_ID_B2 = 1
DESTINATION_ROUTER_ID_B3 = 2
DESTINATION_ROUTER_ID_B4 = 3
METRIC_B1 = 4
METRIC_B2 = 5
METRIC_B3 = 6
METRIC_B4 = 7


def create_response_packet():
    return


def read_response_packet():
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
    elif packet[COMMAND] != 0x02:
        valid_packet = False
        error_msg = "The command field of the packet is incorrect."
    elif packet[VERSION] != 0x02:
        valid_packet = False
        error_msg = "The version field of the packet is incorrect."
    else:
        for entry in range(START_OF_RIP_ENTRIES, len(packet)):
            # TODO add additional checks for content of RIP entry (optional)
            if packet[entry][METRIC_B1] < 0x01 or packet[entry][METRIC_B1] > 0x10:
                valid_packet = False
                error_msg = "The metric for a RIP entry is invalid"
                break
            else:
                valid_packet = True
                error_msg = ""

    return valid_packet, error_msg
