import click
import logging
from pathlib import Path
import sys

from bull import blockdev
from bull import loop
from bull import mapper
from bull import zram

LOG = logging.getLogger(__name__)


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
@click.option('--verbose', '-v', 'loglevel', flag_value='INFO',
              default='WARNING')
@click.option('--debug', '-d', 'loglevel', flag_value='DEBUG')
def cli(loglevel=None):
    logging.basicConfig(level=loglevel)


@cli.command()
@click.option('--part', '-p', type=Size())
@click.option('--offset', '-o', type=Size(), default=0)
@click.option('--size', '-s', type=Size())
@click.option('--backing-size', '-b', type=Size())
@click.option('--name', '-n')
@click.argument('src')
def create(src, part=None, offset=None, size=None,
           name=None, backing_size=None):
    if not zram.check_zram_available():
        raise click.ClickException('ZRAM module is not available')

    src = Path(src)

    if not src.is_block_device():
        loopdev = loop.LoopDevice(src)
        loopdev.create()
        src = loopdev.device

    LOG.info('using source %s', src)

    if part is not None:
        offset = blockdev.get_part_offset_sectors(src, part)
        if size is None:
            size = blockdev.get_part_size_sectors(src, part)
    elif size is None:
        size = blockdev.get_size_sectors(src) - offset

    if backing_size is None:
        backing_size = size

    print('part', part)
    print('offset', offset)
    print('size', size)
    print('backing_size', backing_size)

    try:
        backing = zram.ZramDevice(size=backing_size)
        cow = mapper.MapperDevice(name)
        base = mapper.MapperDevice('{}-base'.format(cow.name))
        base.load("0 {} linear {} {}".format(
            size, src, offset
        ))
        cow.snapshot(base.device, backing.device)
    except mapper.CommandFailed as e:
        print('ERROR:', e, ':', e.result.stderr.decode('utf-8'))
        sys.exit(1)

    print('created', cow.name, cow.device)


@cli.command()
def unmount():
    pass


@cli.command()
def list():
    pass


if __name__ == '__main__':
    cli()
