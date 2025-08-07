class DisconnectedException(Exception):
    def __init__(self, msg):
        self.msg = msg

class AccountNotReadyException(Exception):
    def __init__(self, msg):
        self.msg = msg