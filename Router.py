import setup

class Router:
    def init():
        config = setup.getConfigFile()
        data = setup.getRouterData(config)
        routerId = data[0]
        inputPorts = data[1]
        outputPorts = data[2]
