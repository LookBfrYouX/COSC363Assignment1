import json
import sys

def getConfigFiles():
    configFileNames = []
  try:
      for fileNumber in (1,len(sys.argv)-1):
        configFileNames.append = sys.argv[fileNumber];
    return configFileNames
  except:
    print("An error occured with the input")
    return False


def configFileCheck(configFileNames):
    try:
        for file in configFileNames:
            with open(file) as jsonFile:
                data = json.load(jsonFile)
                routerId = data['router-id']
                if (routerId >= 0 and routerId <= 64000):
                    return True
                else:
                    return False
    except:
        print('An error occured with loading the config file')

def outputRouterList(configFileName):
    try:
        with open(configFileName) as jsonFile:
            data = json.load(jsonFile)
            inputRouters = data['input-routers']
            outputRouters = data['output-routers']
            return (inputRouters, outputRouters)
    except:
        print('An error occured with loading the config file')
