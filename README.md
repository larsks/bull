# Bull

It mounts COWS.

## Examples

### Mounting raspbian from an image

2. Mount a COW device of partition 2 with 256MB available for deltas:

        bull mount --part 2 --size 256M \
          2017-11-29-raspbian-stretch-lite.img /mnt

3. Do some stuff.

4. Umount the COW:

        bull unmount /mnt
