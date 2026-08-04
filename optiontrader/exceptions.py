class DBConnectionException(Exception):
    def __init__(self, msg):
        self.msg = msg

class ResourceNotAvailableException(Exception):
    def __init__(self, msg):
        self.msg = msg

