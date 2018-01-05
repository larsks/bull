class BullError(Exception):
    pass


class CommandFailed(BullError):

    def __init__(self, msg, result):
        super().__init__(msg)
        self.result = result


class NoSuchDevice(BullError):
    pass
