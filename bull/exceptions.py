class BullError(Exception):
    pass


class NoSuchDevice(BullError):
    pass


class NoPartitionMap(BullError):
    pass


class NoDevicesAvailable(BullError):
    pass


class DeviceExists(BullError):
    pass
