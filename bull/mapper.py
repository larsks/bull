import functools
import logging
from pathlib import Path
import subprocess

from bull import blockdev
from bull.exceptions import CommandFailed, NoSuchDevice

LOG = logging.getLogger(__name__)
MAX_DEVICES = 10


class MapperError(Exception):
    pass


class NoDevicesAvailable(MapperError):
    pass


def mapper(*args):
    cli = ['dmsetup'] + [str(arg) for arg in args]
    LOG.debug('running command: %s', cli)
    res = subprocess.run(cli, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise CommandFailed(' '.join(cli), res)

    return res


def check_exists(func):
    @functools.wraps(func)
    def _(self, *args, **kwargs):
        if not self.exists():
            raise NoSuchDevice()
        return func(self, *args, **kwargs)

    return _


class MapperDevice():
    def __init__(self, name=None, prefix='bull'):
        self.prefix = prefix
        self.name = name

        if name is None:
            self.find_next_device()
        else:
            self.create()

        self.device = Path('/dev/mapper/{}'.format(self.name))

    def exists(self):
        try:
            mapper('status', self.name)
        except CommandFailed:
            return False
        else:
            return True

    @check_exists
    def remove(self):
        mapper('remove', self.name)

    def create(self):
        if not self.exists():
            mapper('create', '-n', self.name)

    def find_next_device(self):
        devnum = 0
        while True:
            name = '{}{}'.format(self.prefix, devnum)
            try:
                mapper('create', '-n', name)
                break
            except CommandFailed:
                pass

            devnum += 1
            if devnum > MAX_DEVICES:
                raise NoDevicesAvailable()

        self.name = name

    def load(self, table):
        mapper('suspend', self.name)
        mapper('load', self.name, '--table', table)
        mapper('resume', self.name)

    def table(self):
        res = mapper('table', self.name)
        return res.stdout.splitlines()

    def snapshot(self, srcdev, backingdev, size=None, chunksize=16):
        if size is None:
            size = blockdev.get_size_sectors(srcdev)

        t = '0 {size} snapshot {srcdev} {backingdev} N {chunksize}'.format(
            srcdev=srcdev, backingdev=backingdev,
            size=size, chunksize=chunksize)

        self.load(t)
