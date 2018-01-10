#!/bin/bash

die () {
	echo "ERROR: $1" >&2
	exit ${2:-1}
}

warn () {
	echo "WARNING: $1" >&2
}

info () {
	echo "INFO: $1" >&2
}

while [[ $# -ge 0 ]]; do
	case $1 in
		(--)
			shift
			break
			;;

		(-*)	die "unknown option: $1" 2
			;;

		(*)	break
			;;
	esac
done

bulldevname=$1

if [[ -z $1 ]]; then
	die "you must provide a device name"
fi

# check that user is root
if [[ $(id -u) != 0 ]]; then
	warn "this script typically requires root privileges"
fi

# check that named device exists
if ! dmsetup status ${bulldevname} >& /dev/null; then
	die "no device named $bulldevname"
fi

set -ue

basedevname=${bulldevname}-base

cowdevnum=$(dmsetup table ${bulldevname} | awk '{print $5}')
cowdevpath=/sys/dev/block/${cowdevnum}

if [[ ! -f $cowdevpath/disksize ]]; then
	warn "cow device is not a ramdisk (ignoring)"
	cowdev=''
else
	cowdev=$(readlink ${cowdevpath})
	cowdev=${cowdev##*/}
	info "found zram disk $cowdev"
fi

loopdevnum=$(dmsetup table ${basedevname} | head -1 | awk '{print $4}')
loopdevpath=/sys/dev/block/${loopdevnum}

if [[ ! -d $loopdevpath/loop ]]; then
	warn "origin device is not a loop device"
	loopdev=''
else
	loopdev=$(readlink ${loopdevpath})
	loopdev=${loopdev##*/}
	info "found loop device $loopdev"
fi

warn "removing dm device $bulldevname"
dmsetup remove ${bulldevname}
warn "removing dm device $basedevname"
dmsetup remove ${basedevname}

if [[ ! -z $cowdev ]]; then
	warn "removing cow device $cowdev"
	echo ${cowdevnum##*:} > /sys/class/zram-control/hot_remove
fi

if [[ ! -z $loopdev ]]; then
	warn "removing loop device $loopdev"
	losetup -d /dev/${loopdev}
fi

echo "removed $bulldevname"
