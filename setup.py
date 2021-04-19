import json
import sys


def get_config_file():
    config_filename = ''
    try:
        # gets the second argument from the command line which is the config file
        print(sys.argv[1])
        config_filename = sys.argv[1]
        return config_filename
    except:
        print('An error occurred with the input')


def get_router_data(config_filename):
    """Returns router_id, input_ports and output_ports from config file."""
    try:
        # opens file specified and imports all the data transforming it into a python dictionary from a json file
        with open(config_filename) as jsonFile:
            data = json.load(jsonFile)
            router_id = data['router-id']
            if router_id >= 1024 and router_id <= 64000:
                input_ports = [port.strip() for port in data['input-ports'].split(",")]

                output_ports_string = [port.strip() for port in data['output-ports'].split(",")]
                output_ports = []
                for port in output_ports_string:
                    output_ports.append(port.split("-"))

                for data in output_ports:
                    if data.length == 3 and (data[0] >= 1024 and data[0] <= 64000):
                        return router_id, input_ports, output_ports
                    elif data[0] < 1024 or data[0] > 64000:
                        print('output port not in expected format')
                    else:
                        print('output port not in expected format')
            else:
                print('input port outside expected range')
    except:
        print('An error occurred with loading the config file')
