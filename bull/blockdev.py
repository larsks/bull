import json
import logging
import math
from pathlib import Path
import subprocess

LOG = logging.getLogger(__name__)


def get_sector_size(path):
    path = Path(path)

    if path.is_block_device():
        p = subprocess.run(['blockdev', '--getss', str(path)],
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)

        ssize = p.stdout.decode('utf-8').strip()
        return int(ssize)
    else:
        return 512


def get_size_bytes(path):
    path = Path(path)

    if path.is_block_device():
        p = subprocess.run(['blockdev', '--getsize64', str(path)],
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)

        return int(p.stdout.decode('utf-8').strip())
    else:
        return path.stat().st_size


def get_size_sectors(path):
    path = Path(path)

    if path.is_block_device():
        p = subprocess.run(['blockdev', '--getsz', str(path)],
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)

        return int(p.stdout.decode('utf-8').strip())
    else:
        return math.ceil(path.stat().st_size / 512)


def get_part_table(path):
    LOG.debug('getting partition table for %s', path)
    p = subprocess.run(['sfdisk', '--json', str(path)],
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)

    table = json.loads(p.stdout.decode('utf-8'))
    return table


def get_part_offset_sectors(path, partnum):
    table = get_part_table(path)
    return table['partitiontable']['partitions'][partnum - 1]['start']


def get_part_offset_bytes(path, partnum):
    sectors = get_part_offset_sectors(path, partnum)
    ssize = get_sector_size(path)

    return sectors * ssize


def get_part_size_sectors(path, partnum):
    table = get_part_table(path)
    return table['partitiontable']['partitions'][partnum - 1]['size']


def get_part_size_bytes(path, partnum):
    sectors = get_part_size_sectors(path, partnum)
    ssize = get_sector_size(path)

    return sectors * ssize


def get_mounts():
    mounts = []
    with open('/proc/mounts') as fd:
        for line in fd:
            line = line.split()
            mounts.append((line[0], line[1]))

    return mounts


def is_mounted(device):
    mounts = {dev: path
              for dev, path in get_mounts()}

    return device in mounts
