# qcrild socket permission repair

The private qcrilNrd producer creates radio-owned rild0 and rild1 pathname
sockets with mode 0700. The GNSS client runs as uid 1021 with supplementary
radio group 1001. The installed SELinux policy already permits that client
to search the directory, write the socket node and connect to rild.

This foreground service runs as radio:radio, without requested capabilities.
It watches only /dev/socket/qcrild and examines only rild0 and rild1. A socket
must have owner/group 1001:1001, socket type and mode exactly 0700; the
service adds only group-write, yielding 0720. Other modes/types/owners and
unrelated paths are left alone. O_PATH/NOFOLLOW pins the inode and own
/proc/self/fd traversal avoids redirecting chmod through a replaced path.

This is eventual repair. It does not guarantee execution between producer
bind and listen; the client can still log an initial refusal before retry.
Radio-group clients must also pass SELinux. The helper does not change GNSS
identity, MAC grants, producer blobs, global umask or startup dependencies.

The frozen implementation passed 10 real Linux AF_UNIX tests, including
UID1021 plus radio-group connection, inode/directory replacement, overflow
and rejected ownership/type/mode. Those are not Android/device results.
After changes, build the module and policy, inspect effective permissions,
then test service identity, 0720 readback, GNSS IPC and feature regressions on
a newly built package with SELinux Enforcing. Successful IPC does not prove
satellite positioning or proprietary-protocol acceptance.

The Linux harness needs a disposable root fixture to set ownership and then
drops identities for positive tests. Run only in an isolated test directory:

    g++ -std=c++17 -Wall -Wextra -Werror -DKLEE_SOCKET_WATCHER_TESTING \
        socket_permission_watcher.cpp -o socket_permission_watcher

See test_linux_af_unix.py --help for the fixture interface. Never define
KLEE_SOCKET_WATCHER_TESTING in an Android build; compilation rejects it.
