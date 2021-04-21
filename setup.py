import json
import sys


def get_config_file():
    config_filename = ''
    try:
        # gets the second argument from the command line which is the config file
        config_filename = sys.argv[1]
        return config_filename
    except:
        print('An error occurred with the input.')
        print('Terminating...')
        sys.exit()


def get_router_data(config_filename):
    """Returns router_id, input_ports and output_ports from config file."""
    try:
        # opens file specified and imports all the data transforming it into a python dictionary from a json file
        with open(config_filename) as jsonFile:
            data = json.load(jsonFile)
            router_id = data['router-id']
            if 1 <= int(router_id) <= 64000:
                input_ports = [port.strip() for port in data['input-ports'].split(",")]

                for input_port in input_ports:
                    if 1024 >= int(input_port) >= 64000:
                        print('Input port outside expected range.')
                        sys.exit()

                output_ports_string = [port.strip() for port in data['output-ports'].split(",")]
                output_ports = []
                for port in output_ports_string:
                    output_ports.append(port.split("-"))

                for data in output_ports:
                    if len(data) == 3 and (1024 <= int(data[0]) <= 64000):
                        return router_id, input_ports, output_ports
                    elif int(data[0]) < 1024 or int(data[0]) > 64000:
                        print('Output port not in expected format.')
                        sys.exit()
                    else:
                        print('Output port not in expected format.')
                        sys.exit()
            else:
                print('Router id outside expected range.')
                sys.exit()
    except:
        print('An error occurred with loading the config file.')
        print('Terminating...')
        sys.exit()
