import json
import sys

def getConfigFile():
    configFileName = ''
    try:
        #gets the second argument from the command line which is the config file
        configFileName.append = sys.argv[1];
        return configFileName
    except:
        print('An error occured with the input')


def getRouterData(configFileName):
    '''returns router id, inputPorts and outputPorts from config file'''
    try:
        #opens file specified and imports all the data transforming it into a python dictionary from a json file
        with open(configFileName) as jsonFile:
            data = json.load(jsonFile)
            routerId = data['router-id']
            inputPorts = data['input-ports']
            outputPorts = data['output-ports']
            return (routerId, inputPorts, outputPorts)
    except:
        print('An error occured with loading the config file')
