class IBDisconnectedException(Exception):
    def __init__(self, msg):
        self.msg = msg

class IBAccountNotReadyException(Exception):
    def __init__(self, msg):
        self.msg = msg
        
class IBOrderExcepton(Exception):
    def __init__(self, msg):
        self.msg = msg

class OrderNotFoundException(Exception):
    def __init__(self, msg):
        self.msg = msg