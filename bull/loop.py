import functools
import logging

from bull.blockdev import BlockDevice
from bull.common import run_command

LOG = logging.getLogger(__name__)


losetup = functools.partial(run_command, 'losetup')


class LoopDevice(BlockDevice):
    '''A Linux loop device (like /dev/loop0)'''

    @property
    def backing_file(self):
        with (self.sysfs / 'loop' / 'backing_file').open() as fd:
            backing_file = fd.read().strip()

        return backing_file

    @property
    def offset(self):
        with (self.sysfs / 'loop' / 'offset').open() as fd:
            offset = fd.read().strip()

        return offset

    @classmethod
    def create(kls, backing_file, offset=None, partscan=False,
               readonly=False, sizelimit=None):
        cli = ['--find', '--show']

        if offset is not None:
            cli.append('--offset')
            cli.append(str(offset))

        if readonly:
            cli.append('--read-only')

        if partscan:
            cli.append('--partscan')

        if sizelimit is not None:
            cli.append('--sizelimit')
            cli.append(str(sizelimit))

        cli.append(str(backing_file))

        p = losetup(*cli)
        device = p.stdout.decode('ascii').strip()

        LOG.debug('created loop device %s', device)
        return kls(device)

    def remove(self):
        LOG.debug('removing loop device %s', self.device.name)
        losetup('-d', str(self.device))

    def exists(self):
        return super().exists() and (self.sysfs / 'loop').exists()
