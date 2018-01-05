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
@click.option('--snap-size', '-s', type=Size())
@click.option('--name', '-n')
@click.argument('src')
def create(src, part=None, offset=None, snap_size=None,
           backing_size=None, name=None):

    '''Create a snapshot of the given source.

    Create a copy-on-write snapshot of the given source, using a ramdisk as the
    snapshot backing store.  If the source is not a block device, first map it
    onto a loop device.
    '''

    if not zram.check_zram_available():
        raise click.ClickException('ZRAM module is not available')

    src = Path(src)

    if not src.is_block_device():
        loopdev = loop.LoopDevice.create(src)
        LOG.info('mapped %s to %s', src, loopdev.device)
        src = loopdev
    else:
        src = blockdev.BlockDevice(src)

    if part is not None:
        offset = src.get_part_offset_sectors(part)
        data_sectors = src.get_part_size_sectors(part)
    else:
        data_sectors = src.get_size_sectors() - offset

    data_size = data_sectors * 512

    if snap_size is None:
        snap_size = data_size
    else:
        if snap_size < data_size:
            raise ValueError('requested size cannot be smaller than source')

    snap_sectors = snap_size // 512

    if backing_size is None:
        backing_size = int(min(snap_size * 0.25, MAX_BACKING_SIZE))

    LOG.debug('part %s offset %s data_sectors %s data_size %s',
              part, offset, data_sectors, data_size)
    LOG.debug('snap_size %s snap_sectors %s backing_size %s',
              snap_size, snap_sectors, backing_size)

    try:
        # We reserve a device name by creating a dm device with no table.
        snap = mapper.MapperDevice.create_first_available()

        # Now that we have reserved a device name, we can create the
        # base device. This is a simple linear mapping onto the source,
        # possibly with an offset applied if either --offset or --part
        # were used.
        base = mapper.MapperDevice.create('{}-base'.format(snap.device.name))
        base.table.append(
            mapper.Segment(0, data_sectors,
                           mapper.Linear(src.device, offset)))

        if snap_sectors > data_sectors:
            base.table.append(
                mapper.Segment(data_sectors, (snap_sectors - data_sectors),
                               mapper.Zero()))

        base.load()

        # Create a ramdisk for use as the snapshow backing store.
        backing = zram.ZramDevice.create()
        backing.size = backing_size

        # And finally create the snapshot itself.
        snap.table.append(
            mapper.Segment(0, snap_sectors,
                           mapper.Snapshot(base.device, backing.device)))
        snap.load()
    except subprocess.CalledProcessError as e:
        LOG.error('%s: %s', e, e.stderr.decode('utf-8'))
        sys.exit(1)

    print('created', snap.device)


@cli.command()
@click.argument('name')
def remove(name):
    '''Remove a bull snapshot.

    Tear down the ramdisk, device mapper devices, and loopback
    mounts associated with the bull snapshot. If the bull device is
    mounted, attempt to unmount it first.
    '''

    snap = mapper.MapperDevice.create(name)
    if not snap.exists():
        raise click.ClickException('device {} does not exist'.format(name))
    snap.table.resolve()

    if snap.is_mounted():
        LOG.info('unmounting %s', name)
        subprocess.check_call(['umount', str(snap.device)])

    base = mapper.MapperDevice.create('{}-base'.format(name))
    base.table.resolve()

    backingdev = snap.table[0].target.backing
    srcdev = base.table[0].target.device

    LOG.debug('got source device %s', srcdev)
    LOG.debug('got backing device %s', backingdev)

    backing = zram.ZramDevice(backingdev)

    if srcdev.startswith('/dev/loop'):
        loopdev = loop.LoopDevice(srcdev)
    else:
        loopdev = None

    try:
        snap.remove()
        backing.remove()
        base.remove()

        if loopdev:
            loopdev.remove()
    except subprocess.CalledProcessError as e:
        LOG.error('%s: %s', e, e.stderr.decode('utf-8'))
        sys.exit(1)

    print('removed', name)


@cli.command()
def list():
    '''List existing bull snapshots.'''

    try:
        print('\n'.join(mapper.list_devices()))
    except subprocess.CalledProcessError as e:
        LOG.error('%s: %s', e, e.stderr.decode('utf-8'))
        sys.exit(1)


if __name__ == '__main__':
    cli()
