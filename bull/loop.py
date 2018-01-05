import logging
from pathlib import Path
import subprocess

from bull.exceptions import CommandFailed, NoSuchDevice

LOG = logging.getLogger(__name__)


def losetup(*args):
    cli = ['losetup'] + [str(arg) for arg in args]
    LOG.debug('running command: %s', cli)
    res = subprocess.run(cli, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise CommandFailed(' '.join(cli), res)

    return res


class LoopDevice():
    def __init__(self, src, device=None, offset=None):
        self.offset = 0 if offset is None else offset
        self.device = device
        self.src = src

    def create(self):
        cli = ['--show']

        if self.offset:
            cli.append('-o')
            cli.append('{}'.format(self.offset))

        if self.device is None:
            cli.append('-f')
        else:
            cli.append(self.device)

        cli.append(self.src)
        res = losetup(*cli)

        self.device = res.stdout.decode('utf-8').strip()

    def remove(self):
        losetup('-d', self.device)
