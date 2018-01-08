import logging
from pathlib import Path

from bull.blockdev import BlockDevice

LOG = logging.getLogger(__name__)


def check_zram_available():
    return Path('/sys/class/zram-control').exists()


class ZramDevice(BlockDevice):
    control_path = Path('/sys/class/zram-control')

    @classmethod
    def create(kls, minor=None):
        if minor is None:
            with (kls.control_path / 'hot_add').open() as fd:
                minor = fd.read().strip()

        LOG.debug('created new zram device zram%s', minor)
        return kls('/dev/zram{}'.format(minor))

    def remove(self):
        LOG.debug('removing zram device %s', self.device.name)
        with (self.control_path / 'hot_remove').open('w') as fd:
            fd.write('{}'.format(self.minor))

    def get_size(self):
        with (self.sysfs / 'disksize').open() as fd:
            size = fd.readline().strip()

        return int(size)

    def set_size(self, size):
        LOG.debug('set size of zram device %s to %s',
                  self.device.name, size)
        with (self.sysfs / 'disksize').open('w') as fd:
            fd.write('{}'.format(size))

    size = property(get_size, set_size)

    def reset(self):
        LOG.debug('resetting zram device %s', self.device.name)
        with (self.sysfs / 'reset').open('w') as fd:
            fd.write('1')
