import attr
import functools
import logging
import subprocess

from bull.blockdev import BlockDevice
from bull.common import run_command
from bull.exceptions import NoDevicesAvailable, DeviceExists

LOG = logging.getLogger(__name__)
MAX_DEVICES = 10


dmsetup = functools.partial(run_command, 'dmsetup')


def resolve_device(dev):
    '''Derive a device name from a major:minor pair'''

    if dev.startswith('/dev'):
        return dev

    try:
        with open('/sys/dev/block/{}/dm/name'.format(dev)) as fd:
            name = fd.read().strip()
            return '/dev/mapper/{}'.format(name)
    except FileNotFoundError:
        with open('/sys/dev/block/{}/uevent'.format(dev)) as fd:
            uevent = {k: v.strip() for k, v in [line.split('=', 1)
                                                for line in fd]}

        return '/dev/{DEVNAME}'.format(**uevent)


def list_devices(prefix='bull'):
    '''Return a list of device mapper snapshot device names that start with the
    given prefix.
    '''

    p = dmsetup('ls', '--target', 'snapshot')
    return [line.split()[0].decode('ascii') for line in p.stdout.splitlines()]


class Table(list):
    '''Segment table for a device mapper device.'''

    @classmethod
    def from_string(kls, table):
        return kls([Segment.from_string(segment)
                    for segment in table.splitlines()
                    if segment.strip()])

    def resolve(self):
        for segment in self:
            segment.target.resolve()

    def __str__(self):
        return '\n'.join(str(x) for x in self)


@attr.s
class Segment():
    '''A single segment in a device mapper table.'''

    start = attr.ib(converter=int)
    sectors = attr.ib(converter=int)
    target = attr.ib()

    @classmethod
    def from_string(kls, segment):
        start, size, target = segment.split(None, 2)
        return kls(start, size, Target.from_string(target))

    def __str__(self):
        return '{self.start} {self.sectors} {self.target}'.format(self=self)


@attr.s
class Target():
    '''A target in a device mapper device table'''

    device_attrs = []

    @classmethod
    def from_string(kls, target):
        _type, *args = target.split()

        if _type == 'linear':
            return Linear(*args)
        elif _type == 'snapshot':
            return Snapshot(*args)
        elif _type == 'zero':
            return Zero(*args)
        elif _type == 'thin-pool':
            return Thinpool(*args)
        elif _type == 'thin':
            return Thin(*args)
        else:
            raise ValueError('unknown target description: {}'.format(target))

    def resolve(self):
        for attrname in self.device_attrs:
            setattr(self, attrname,
                    resolve_device(getattr(self, attrname)))

    def __str__(self):
        target_type = self.__class__.__name__.lower()
        attrs = [target_type] + [getattr(self, x.name)
                                 for x in attr.fields(self.__class__)]
        return ' '.join(str(x) for x in attrs if x is not None)


@attr.s
class Zero(Target):
    '''https://www.kernel.org/doc/Documentation/device-mapper/zero.txt'''
    pass


@attr.s
class Linear(Target):
    '''https://www.kernel.org/doc/Documentation/device-mapper/linear.txt'''
    device_attrs = ['device']

    device = attr.ib(converter=str)
    offset = attr.ib(converter=int, default=0)


@attr.s
class Snapshot(Target):
    '''https://www.kernel.org/doc/Documentation/device-mapper/snapshot.txt'''
    device_attrs = ['origin', 'backing']

    def persistent_converter(arg):
        if isinstance(arg, str) and arg.upper() in 'PN':
            return arg.upper()
        elif isinstance(arg, bool):
            return 'P' if arg else 'N'
        else:
            raise ValueError(arg)

    origin = attr.ib(converter=str)
    backing = attr.ib(converter=str)
    persistent = attr.ib(converter=persistent_converter, default=False)
    chunksize = attr.ib(converter=int, default=16)


@attr.s
class Thinpool(Target):
    '''https://www.kernel.org/doc/Documentation/device-mapper/thin-provisioning.txt'''  # NOQA

    device_attrs = ['metadata_dev', 'data_dev']

    metadata_dev = attr.ib(converter=str)
    data_dev = attr.ib(converter=str)
    blocksize = attr.ib(converter=int)
    lwm = attr.ib(converter=int)
    argc = attr.ib(converter=int)


@attr.s
class Thin(Target):
    '''https://www.kernel.org/doc/Documentation/device-mapper/thin-provisioning.txt'''  # NOQA

    device_attrs = ['pool_dev']

    pool_dev = attr.ib(converter=str)
    dev_id = attr.ib(converter=int)
    origin = attr.ib(default=None)


class MapperDevice(BlockDevice):
    '''A device-mapper device.

    See https://www.kernel.org/doc/Documentation/device-mapper/ for
    more information.
    '''

    def __init__(self, device):
        super().__init__(device)
        self.table = self.get_table_from_device()

    def get_table_from_device(self):
        res = dmsetup('table', self.device.name)
        return Table.from_string(res.stdout.decode('ascii'))

    @classmethod
    def create(kls, name, exclusive=False):
        LOG.debug('creating dm device %s', name)
        try:
            dmsetup('status', name)
            if exclusive:
                raise DeviceExists(name)
        except subprocess.CalledProcessError:
            dmsetup('create', name, '--notable')

        return kls('/dev/mapper/{}'.format(name))

    @classmethod
    def create_first_available(kls, prefix='bull'):
        LOG.debug('looking for available device')
        for devnum in range(MAX_DEVICES):
            devname = '{}{}'.format(prefix, devnum)
            LOG.debug('checking device %s', devname)
            try:
                dmsetup('create', devname, '--notable')
            except subprocess.CalledProcessError:
                pass
            else:
                LOG.debug('found device %s', devname)
                break
        else:
            raise NoDevicesAvailable()

        return kls('/dev/mapper/{}'.format(devname))

    def remove(self):
        LOG.debug('removing dm device %s', self.device.name)
        dmsetup('remove', self.device.name)

    def load(self):
        LOG.debug('loading table for dm device %s', self.device.name)
        dmsetup('suspend', self.device.name)
        dmsetup('load', self.device.name,
                input=str(self.table).encode('ascii'))
        dmsetup('resume', self.device.name)

    def refresh(self):
        LOG.debug('reading table for dm device %s', self.device.name)
        self.table = self.get_table_from_device()
