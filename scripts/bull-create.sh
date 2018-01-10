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

to_bytes () {
	local _val=$1
	local _scale

	case $_val in
		*T)	_val=${_val::-1}
			_scale=$(( 1024 * 1024 * 1024 * 1024 ))
			;;
		*G)	_val=${_val::-1}
			_scale=$(( 1024 * 1024 * 1024 ))
			;;
		*M)	_val=${_val::-1}
			_scale=$(( 1024 * 1024 ))
			;;
		*K)	_val=${_val::-1}
			_scale=$(( 1024 ))
			;;

		*[0-9])	_scale=1
			;;
	esac

	echo $(( _val * _scale ))
}

while [[ $# -ge 0 ]]; do
	case $1 in
		(--part|-p)
			part=$2
			shift 2
			;;

		(--snap-size|-s)
			snap_size=$(to_bytes $2)
			shift 2
			;;

		(--cow-size|-c)
			cow_size=$(to_bytes $2)
			shift 2
			;;

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

src=$1

if [[ -z $1 ]]; then
	die "you must provide a source file or device"
fi

# check that user is root
if [[ $(id -u) != 0 ]]; then
	warn "this script typically requires root privileges"
fi

# check that source is a file or block device
if [[ ! ( -f $1 || -b $1 ) ]]; then
	die "source must be a file or block device"
fi

# ensure zram support is available
if [[ ! -d /sys/class/zram-control ]]; then
	if ! modprobe zram >& /dev/null; then
		die "zram support is not available"
	fi
fi

# ensure device mapper is available
if ! dmsetup version >& /dev/null; then
	die "dmsetup failed"
fi

set -ue

if [[ -f $src ]]; then
	srcdev=$(losetup --find --show --read-only $src)
	info "mapped $src to block device $srcdev"
else
	srcdev=$src
fi

info "using device $srcdev"

if [[ $part ]]; then
	info "getting size and offset of partition $part"

	res=($(sfdisk --json $srcdev |
		jq ".partitiontable.partitions[$((part - 1))] | .start, .size"))

	base_offset=${res[0]}
	base_size=${res[1]}
else
	base_offset=0
	base_size=$(blockdev --getsz $srcdev)
fi

if [[ ${snap_size:-0} -eq 0 ]]; then
	snap_size=$base_size
fi

# adjust to multiple of 4096
snap_size=$(( 4096 * (snap_size/4096) ))

if [[ ${cow_size:-0} -eq 0 ]]; then
	cow_size=$(echo $snap_size 0.25 \* p | dc)
fi

# find first available bull device
n=0
while :; do
	dmsetup create --notable bull${n} && break
	let n++
	if [[ $n -ge 10 ]]; then
		die "no bull devices available"
	fi
done
bullname=bull${n}
bulldev=/dev/mapper/${bullname}

info "creating bull device $bullname"

# create base device
basename=${bullname}-base
basedev=/dev/mapper/${basename}
info "creating device ${basename}"
dmsetup create ${basename} <<EOF
0 $base_size linear $srcdev $base_offset
$base_size $((snap_size/512 - base_size)) zero
EOF

# create zram device
info "creating zram backing store"
cowdevnum=$(cat /sys/class/zram-control/hot_add)
cowdevname=zram${cowdevnum}
cowdev=/dev/${cowdevname}
echo $cow_size > /sys/block/$cowdevname/disksize

# update table in snap device
info "loading table into $bullname"
cat <<EOF | tee table | dmsetup load ${bullname}
0 $((snap_size / 512)) snapshot $basedev $cowdev N 16
EOF
dmsetup resume ${bullname}
