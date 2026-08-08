#!/bin/sh
# Chamber: filesystem view excludes the repository; only /work is writable.
# MODE=broken deliberately exposes the repo — the negative control.
CH="$1"; MODE="$2"; PROBE="$3"
mkdir -p "$CH"/proc "$CH"/work "$CH"/usr "$CH"/lib "$CH"/lib64 "$CH"/bin "$CH"/sbin "$CH"/etc "$CH"/dev
cp "$PROBE" "$CH/probe.sh" || exit 91
# Mountpoints must exist BEFORE the root goes read-only.
[ "$MODE" = "broken" ] && mkdir -p "$CH${REPO_ROOT:-/home/user/uniimente-kernel}"
mount --bind "$CH" "$CH" || exit 92
mount -o remount,bind,ro "$CH" || exit 93
for d in usr lib lib64 bin sbin etc; do
  [ -e "/$d" ] || continue
  mount --bind "/$d" "$CH/$d" || exit 94
  mount -o remount,bind,ro "$CH/$d" || true
done
mount -t proc none "$CH/proc" || true
mount -t tmpfs -o size=1m none "$CH/dev" || true
mknod "$CH/dev/null" c 1 3 2>/dev/null; chmod 666 "$CH/dev/null" 2>/dev/null
mount -t tmpfs -o size=64m none "$CH/work" || exit 95   # the ONLY writable path
[ "$MODE" = "broken" ] && { mount --bind ${REPO_ROOT:-/home/user/uniimente-kernel} "$CH${REPO_ROOT:-/home/user/uniimente-kernel}" || exit 96; }
exec chroot "$CH" /usr/bin/env -i PATH=/usr/bin:/bin HOME=/work /bin/sh /probe.sh
