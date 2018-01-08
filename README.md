# Bull

It mounts COWS.

## Examples

### Working with a Raspbian image

Create the COW device:

    # bull create --snap-size 3G --part 2 --backing-size 512MB \
      /home/lars/Downloads/2017-11-29-raspbian-stretch-lite.img
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
