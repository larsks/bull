import functools
import logging
from pathlib import Path

from bull.exceptions import NoSuchDevice

LOG = logging.getLogger(__name__)


def check_exists(func):
    @functools.wraps(func)
    def _(self, *args, **kwargs):
        self._check_exists()
        return func(self, *args, **kwargs)

    return _


class ZramDevice():
    def __init__(self, devnum=None, size=None):
        if devnum is None:
            devnum = self.allocate_device()

        self.devnum = devnum
        self.name = 'zram{}'.format(devnum)
        self.path = Path('/sys/block/zram{}'.format(devnum))
        self.device = '/dev/zram{}'.format(devnum)

        if size is not None:
            self.size = size

    def allocate_device(self):
        control = Path('/sys/class/zram-control/hot_add')
        with control.open() as fd:
            dev = fd.readline()

        LOG.debug('allocated zram device: %s', dev)
        return int(dev)

    def _check_exists(self):
        if not self.path.exists():
            raise NoSuchDevice(self.name)

    @check_exists
    def get_size(self):
        sizepath = self.path / 'disksize'
        with sizepath.open() as fd:
            size = fd.readline()

        return int(size)

    @check_exists
    def set_size(self, size):
        sizepath = self.path / 'disksize'
        with sizepath.open('w') as fd:
            fd.write('{}'.format(size))
            fd.write('\n')

    size = property(get_size, set_size)

    @check_exists
    def remove(self):
        control = Path('/sys/class/zram-control/hot_remove')
        with control.open('w') as fd:
            fd.write('{}'.format(self.devnum))
            fd.write('\n')

    @check_exists
    def reset(self):
        control = self.path / 'reset'
        with control.open('w') as fd:
            fd.write('1')
            fd.write('\n')


def check_zram_available():
    return Path('/sys/class/zram-control').exists()
