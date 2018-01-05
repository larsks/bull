import logging
import subprocess

from bull.blockdev import BlockDevice

LOG = logging.getLogger(__name__)


class LoopDevice(BlockDevice):
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
        cli = ['losetup', '--find', '--show']

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

        p = subprocess.run(cli,
                           check=True,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)

        return kls(p.stdout.decode('ascii').strip())

    def remove(self):
        subprocess.run(['losetup', '-d', str(self.device)],
                       check=True,
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)

    def exists(self):
        return super().exists() and (self.sysfs / 'loop').exists()
