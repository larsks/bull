import click
import logging
from pathlib import Path
import subprocess
import sys

from bull import blockdev
from bull import loop
from bull import mapper
from bull import zram

LOG = logging.getLogger(__name__)
MAX_BACKING_SIZE = 2**30


class Size(click.ParamType):
    name = 'size'

    def convert(self, value, param, ctx):
        if str(value).isdigit():
            return int(value)

        _value, unit = value[:-1], value[-1]
        _value = int(_value)
        unit = unit.lower()

        if unit == 'b':
            return _value
        elif unit == 'k':
            return _value * 1024
        elif unit == 'm':
            return _value * 1024 * 1024
        elif unit == 'g':
            return _value * 1024 * 1024 * 1024
        else:
            raise ValueError(value)


@click.group()
@click.option('--quiet', '-q', 'loglevel', flag_value='WARNING',
              default=True)
@click.option('--verbose', '-v', 'loglevel', flag_value='INFO')
@click.option('--debug', '-d', 'loglevel', flag_value='DEBUG')
def cli(loglevel=None):
    logging.basicConfig(level=loglevel)


@cli.command()
@click.option('--part', '-p', type=Size())
@click.option('--offset', '-o', type=Size(), default=0)
@click.option('--backing-size', '-b', type=Size())
@click.option('--size', '-s', type=Size())
@click.option('--name', '-n')
@click.argument('src')
def create(src, part=None, offset=None, size=None,
           name=None, backing_size=None):

    '''Create a snapshot of the given source.

    Create a copy-on-write snapshot of the given source, using a ramdisk as the
    snapshot backing store.  If the source is not a block device, first map it
    onto a loop device.
    '''

    if not zram.check_zram_available():
        raise click.ClickException('ZRAM module is not available')

    src = Path(src)

    if not src.is_block_device():
        loopdev = loop.LoopDevice(src=src)
        loopdev.create()

        LOG.info('mapped %s to %s', src, loopdev.device)
        src = loopdev.device

    if part is not None:
        offset = blockdev.get_part_offset_sectors(src, part)
        datasize = blockdev.get_part_size_sectors(src, part)
    else:
        datasize = blockdev.get_size_sectors(src) - offset

    if size is None:
        size = datasize
    elif size < datasize:
        raise ValueError('requested size cannot be smaller than source')

    size_sectors = int(size / 1024 * 2)

    if backing_size is None:
        backing_size = int(min(size * 0.25, MAX_BACKING_SIZE))

    LOG.debug('part %s offset %s datasize %s size %s '
              'size_sectors %s backing_size %s',
              part, offset, datasize, size, size_sectors, backing_size)

    try:
        # We reserve a device name by creating a dm device with no table.
        snap = mapper.MapperDevice(name)
        snap.create()

        # Now that we have reserved a device name, we can create the
        # base device. This is a simple linear mapping onto the source,
        # possibly with an offset applied if either --offset or --part
        # were used.
        base = mapper.MapperDevice('{}-base'.format(snap.name))
        base.create()
        table = [
            "0 {} linear {} {}".format(datasize, src, offset),
        ]

        if size_sectors > datasize:
            table.append("{} {} zero".format(datasize, (size_sectors - datasize)))

        base.load('\n'.join(table))

        # Create a ramdisk for use as the snapshow backing store.
        backing = zram.ZramDevice(size=backing_size)

        # And finally create the snapshot itself.
        snap.snapshot(base.device, backing.device)
    except mapper.CommandFailed as e:
        LOG.error('%s: %s', e, e.result.stderr.decode('utf-8'))
        sys.exit(1)

    print('created', snap.name, snap.device)


@cli.command()
@click.argument('name')
def remove(name):
    '''Remove a bull snapshot.

    Tear down the ramdisk, device mapper devices, and loopback
    mounts associated with the bull snapshot. If the bull device is
    mounted, attempt to unmount it first.
    '''

    snap = mapper.MapperDevice(name=name)
    if not snap.exists():
        raise click.ClickException('device {} does not exist'.format(name))

    if blockdev.is_mounted(snap.device):
        LOG.info('unmounting %s', name)
        subprocess.check_call(['umount', str(snap.device)])

    base = mapper.MapperDevice(name='{}-base'.format(name))
    backingdevnum = snap.table()[0].split()[4].decode('utf-8').split(':')[1]
    backing = zram.ZramDevice(devnum=backingdevnum)
    srcdevnum = base.table()[0].split()[3].decode('utf-8')
    srcdev = blockdev.devnum_to_name(srcdevnum)

    if srcdev.startswith('loop'):
        loopdev = loop.LoopDevice(device='/dev/{}'.format(srcdev))
    else:
        loopdev = None

    try:
        snap.remove()
        backing.remove()
        base.remove()

        if loopdev:
            loopdev.remove()
    except mapper.CommandFailed as e:
        LOG.error('%s: %s', e, e.result.stderr.decode('utf-8'))
        sys.exit(1)

    print('removed', name)


@cli.command()
def list():
    '''List existing bull snapshots.'''

    try:
        print('\n'.join(mapper.list_devices()))
    except mapper.CommandFailed as e:
        LOG.error('%s: %s', e, e.result.stderr.decode('utf-8'))
        sys.exit(1)


if __name__ == '__main__':
    cli()
