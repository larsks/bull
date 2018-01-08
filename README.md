# Bull

It mounts COWS.

## Usage

### Create

    Usage: bull create [OPTIONS] SRC

      Create a snapshot of the given source.

      Create a copy-on-write snapshot of the given source, using a ramdisk as
      the snapshot backing store.  If the source is not a block device, first
      map it onto a loop device.

    Options:
      -p, --part SIZE
      -o, --offset SIZE
      -b, --backing-size SIZE
      -s, --snap-size SIZE
      -n, --name TEXT
      --help                   Show this message and exit.

### Remove

    Usage: bull remove [OPTIONS] NAME

      Remove a bull snapshot.

      Tear down the ramdisk, device mapper devices, and loopback mounts
      associated with the bull snapshot. If the bull device is mounted, attempt
      to unmount it first.

    Options:
      --help  Show this message and exit.

### List

    Usage: bull list [OPTIONS]

      List existing bull snapshots.

    Options:
      --help  Show this message and exit.

## Examples

### Working with a Raspbian image

Create the COW device:

    # bull create --snap-size 3G --part 2 --backing-size 512MB \
      2017-11-29-raspbian-stretch-lite.img
    created /dev/mapper/bull0

Mount it:

    # mount /dev/mapper/bull0 /mnt

Resize the filesystem to take advantage of the additional space we
allocated using `--snap-size`:

    # resize2fs /dev/mapper/bull0
    resize2fs 1.43.3 (04-Sep-2016)
    Filesystem at /dev/mapper/bull0 is mounted on /mnt; on-line resizing required
    old_desc_blocks = 1, new_desc_blocks = 1
    The filesystem on /dev/mapper/bull0 is now 786432 (4k) blocks long.

Do some stuff:

    # systemd-nspawn -D /mnt

Finish up (`bull` will automatically unmount the COW device if it is
mounted):

    # bull remove bull0

## Details

When you run:

    bull create --snap-size 3G --part 2 --backing-size 512MB \
      2017-11-29-raspbian-stretch-lite.img

The following happens:

- Map the source file to a loop device using `losetup`.

- Create a new device-mapper device named `bull0` with no table.

- Create a new device-mapper device named `bull0-base` with no table.

- Create a table for `bull0-base` that looks like:

        0 3534848 linear /dev/loop0 94208
        3534848 6950912 zero

  The first segment maps onto the loop device we created in the
  earlier step.  The second statement simply fills in the difference
  between the size of our source and the size requested with
  `--snap-size`.

- Create a 512MB ramdisk for use as the backing store.

- Create a table for `bull0` that looks like:

        0 10485760 snapshot /dev/mapper/bull0-base /dev/zram0 N 16


## Additional reading

The kernel documentation includes information about the device mapper
targets used in this code:

- [zero](https://www.kernel.org/doc/Documentation/device-mapper/zero.txt)
- [linear](https://www.kernel.org/doc/Documentation/device-mapper/linear.txt)
- [snapshot](https://www.kernel.org/doc/Documentation/device-mapper/snapshot.txt)
