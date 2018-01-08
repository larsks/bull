import attr
import json
from pathlib import Path
import subprocess

from bull.exceptions import NoPartitionMap
from bull.common import run_command


def get_mounts():
    mounts = []
    with open('/proc/mounts') as fd:
        for line in fd:
            line = line.split()
            mounts.append((line[0], line[1]))
    return mounts


@attr.s
class BlockDevice():
    device = attr.ib(converter=Path)

    def get_device_info(self):
        with (self.sysfs / 'dev').open() as fd:
            return (int(x) for x in (fd.read().strip().split(':')))

    @property
    def sysfs(self):
        return Path('/sys/block') / self.realdevice.name

    @property
    def realdevice(self):
        return self.device.resolve()

    @property
    def major(self):
        major, minor = self.get_device_info()
        return major

    @property
    def minor(self):
        major, minor = self.get_device_info()
        return minor

    def get_sector_size(self):
        p = run_command('blockdev', '--getss', str(self.device))
        return int(p.stdout.decode('ascii').strip())

    def get_size_bytes(self):
        p = run_command('blockdev', '--getsize64', str(self.device))
        return int(p.stdout.decode('ascii').strip())

    def get_size_sectors(self):
        p = run_command('blockdev', '--getsz', str(self.device))
        return int(p.stdout.decode('ascii').strip())

    def get_part_table(self):
        try:
            p = run_command('sfdisk', '--json', str(self.device))
        except subprocess.CalledProcessError:
            raise NoPartitionMap(self)

        table = json.loads(p.stdout.decode('ascii'))
        return table

    def get_part_offset_sectors(self, partnum):
        table = self.get_part_table()
        return table['partitiontable']['partitions'][partnum - 1]['start']

    def get_part_size_sectors(self, partnum):
        table = self.get_part_table()
        return table['partitiontable']['partitions'][partnum - 1]['size']

    def get_part_size_bytes(self, partnum):
        sectors = self.get_part_size_sectors()
        ssize = self.get_sector_size()
        return sectors * ssize

    def exists(self):
        return self.device.exists()

    def is_mounted(self):
        mounts = {dev: path
                  for dev, path in get_mounts()}

        return str(self.device) in mounts
