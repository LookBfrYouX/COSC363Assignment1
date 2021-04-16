import setup
import json
from Router import Router
import select

BUFFER_SIZE = 1024


def main():
    # TODO setup
    # TODO bind sockets
    config = setup.get_config_file()
    data_from_config = setup.get_router_data(config)
    router1 = Router(data_from_config)
    print(router1)

    # TODO sockets
    sockets = []
    while True:
        readable, writable, in_error = select.select(sockets, sockets, [])

        for socket in readable:
            response_packet = socket.recvfrom(BUFFER_SIZE)
            # TODO recv
            blah = ""
        for socket in writable:
            # TODO send
            blah2 = ""


main()
