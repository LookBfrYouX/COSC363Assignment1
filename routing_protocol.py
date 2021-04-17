import setup
import json
from Router import Router
import select

BUFFER_SIZE = 1024


def main():
    # TODO setup
    # TODO bind sockets
    # TODO sockets for each router
    config = setup.get_config_file()
    data_from_config = setup.get_router_data(config)
    sockets = []
    router1 = Router(data_from_config, sockets)
    print(router1)
    routers = [router1]

    while True:

        for router in routers:
            readable, writeable = select.select(router.sockets, router.sockets, [])

            for socket in readable:
                temporary_storage = socket.recvfrom(BUFFER_SIZE)
                response_packet = json.loads(temporary_storage.decode('utf-8'))
                router.read_response_packet(response_packet)

            for port in router.output_ports:
                port_components = port.split("-")
                destination_router_id = port_components[2]
                if len(writeable) > 0:  # At least one socket is free to send a response packet
                    socket = writeable[0]  # doesn't matter what socket is used to send, so select first one.
                    response_packet = router.create_response_packet(destination_router_id)
                    response_packet_bytes = json.dumps(response_packet).encode('utf-8')
                    socket.sendto(response_packet_bytes, port)


main()
