import attr
import json
from pathlib import Path
import subprocess

from bull.common import run_command
from bull.exceptions import NoPartitionMap


def get_mounts():
    mounts = []
    with open('/proc/mounts') as fd:
        for line in fd:
            line = line.split()
            mounts.append((line[0], line[1]))
    return mounts


@attr.s
class BlockDevice():
    '''Base class for our other block device classes.'''

    device = attr.ib(converter=Path)

    def get_device_info(self):
        with (self.sysfs / 'dev').open() as fd:
            return (int(x) for x in (fd.read().strip().split(':')))

    @property
    def sysfs(self):
        return Path('/sys/block') / self.realdevice.name

    @property
    def realdevice(self):
        '''Return canonical name for a device.

        Block devices can be known by different names.  You may know
        something as /dev/mapper/foo, but it may also be known as
        /dev/dm-10, and this is the name that we need to find the
        device in /sys.
        '''

        return self.device.resolve()

    @property
    def major(self):
        major, minor = self.get_device_info()
        return major

    @property
    def minor(self):
        major, minor = self.get_device_info()
        return minor

    def get_size_bytes(self):
        '''Return the device size in bytes.'''

        p = run_command('blockdev', '--getsize64', str(self.device))
        return int(p.stdout.decode('ascii').strip())

    def get_size_sectors(self):
        '''Return the device size in 512-byte sectors.'''
        p = run_command('blockdev', '--getsz', str(self.device))
        return int(p.stdout.decode('ascii').strip())

    def get_part_table(self):
        '''Return the partition table of the device.'''
        try:
            p = run_command('sfdisk', '--json', str(self.device))
        except subprocess.CalledProcessError:
            raise NoPartitionMap(self)

        table = json.loads(p.stdout.decode('ascii'))
        return table

    def get_part_offset_sectors(self, partnum):
        '''Get the offset of a partition in 512-byte sectors.'''

        table = self.get_part_table()
        return table['partitiontable']['partitions'][partnum - 1]['start']

    def get_part_size_sectors(self, partnum):
        '''Get the size of a partition in 512-byte sectors.'''

        table = self.get_part_table()
        return table['partitiontable']['partitions'][partnum - 1]['size']

    def get_part_size_bytes(self, partnum):
        '''Get the size of a partition in bytes.'''

        sectors = self.get_part_size_sectors()
        return sectors * 512

    def exists(self):
        '''Returns True if the device path exists, False otherwise.'''

        return self.device.exists()

    def is_mounted(self):
        '''Returns True if the device is mounted, False otherwise.'''

        mounts = {dev: path
                  for dev, path in get_mounts()}

        return str(self.device) in mounts
