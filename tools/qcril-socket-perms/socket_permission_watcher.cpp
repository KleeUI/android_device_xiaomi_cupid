// Candidate only: eventual DAC repair for two qcrild pathname sockets.
// No bind/listen interposition, global umask change, UID change, or capability.
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif

#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/inotify.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <unistd.h>

#include <array>
#include <string>
#include <utility>

#if defined(__ANDROID__)
#include <android/log.h>
#endif

#if defined(__ANDROID__) && defined(KLEE_SOCKET_WATCHER_TESTING)
#error "The Android production binary must not accept a test directory"
#endif

namespace {
constexpr char kDirectory[] = "/dev/socket/qcrild";
constexpr std::array<const char*, 2> kNames{{"rild0", "rild1"}};
constexpr uid_t kRadioUid = 1001;
constexpr gid_t kRadioGid = 1001;
constexpr mode_t kDirectoryMode = 0750;
constexpr mode_t kExpectedMode = 0700;
constexpr mode_t kDesiredMode = kExpectedMode | S_IWGRP;
constexpr int kRescanMilliseconds = 1000;
constexpr uint32_t kMask = IN_CREATE | IN_MOVED_TO | IN_MOVED_FROM |
        IN_DELETE | IN_ATTRIB | IN_DELETE_SELF | IN_MOVE_SELF | IN_UNMOUNT |
        IN_ONLYDIR;
volatile sig_atomic_t gStop = 0;

void Stop(int) {
    gStop = 1;
}

void Log(bool error, const char* format, ...) {
    char text[768];
    va_list arguments;
    va_start(arguments, format);
    vsnprintf(text, sizeof(text), format, arguments);
    va_end(arguments);
#if defined(__ANDROID__)
    __android_log_write(error ? ANDROID_LOG_ERROR : ANDROID_LOG_INFO,
                        "KleeQcrilSocketPerms", text);
#else
    fprintf(stderr, "%s %s\n", error ? "ERROR" : "INFO", text);
    fflush(stderr);
#endif
}

class Fd {
  public:
    explicit Fd(int value = -1) : value_(value) {}
    ~Fd() { reset(); }
    Fd(const Fd&) = delete;
    Fd& operator=(const Fd&) = delete;
    int get() const { return value_; }
    bool valid() const { return value_ >= 0; }
    void reset(int value = -1) {
        if (value_ >= 0) close(value_);
        value_ = value;
    }
  private:
    int value_;
};

bool SameInode(const struct stat& first, const struct stat& second) {
    return first.st_dev == second.st_dev && first.st_ino == second.st_ino;
}

mode_t Permissions(const struct stat& information) {
    return information.st_mode & 07777;
}

std::string ProcFd(int fd) {
    return "/proc/self/fd/" + std::to_string(fd);
}

class Watcher {
  public:
    explicit Watcher(std::string directory) : directory_(std::move(directory)) {}

    int Run() {
        Log(false, "started uid=%u gid=%u directory=%s scope=rild0,rild1 eventual-repair",
            static_cast<unsigned>(geteuid()), static_cast<unsigned>(getegid()),
            directory_.c_str());
        while (!gStop) {
            if (!directoryFd_.valid()) {
                if (!Attach()) {
                    poll(nullptr, 0, kRescanMilliseconds);
                    continue;
                }
                Scan();  // Watch is attached before the initial scan.
            }
            if (!IsCurrentDirectory()) {
                Detach("directory-replaced-or-unavailable");
                continue;
            }
            struct pollfd descriptor { inotifyFd_.get(), POLLIN, 0 };
            const int ready = poll(&descriptor, 1, kRescanMilliseconds);
            if (ready < 0) {
                if (errno == EINTR) continue;
                Log(true, "poll-failed errno=%d", errno);
                Detach("poll-failed");
                continue;
            }
            if (ready > 0) {
                if (descriptor.revents & (POLLERR | POLLHUP | POLLNVAL)) {
                    Detach("inotify-descriptor-unavailable");
                    continue;
                }
                if (!DrainEvents()) {
                    Detach("watch-lost");
                    continue;
                }
            }
            // A bounded periodic rescan also recovers missed/coalesced events.
            // Only the two fixed basenames are examined, never a directory walk.
            if (!IsCurrentDirectory()) {
                Detach("directory-replaced-or-unavailable");
                continue;
            }
            Scan();
        }
        Detach("stopping");
        Log(false, "stopped");
        return 0;
    }

  private:
    bool OpenDirectory(Fd* descriptor, struct stat* information) {
        descriptor->reset(open(directory_.c_str(),
            O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
        if (!descriptor->valid()) return false;
        if (fstat(descriptor->get(), information) != 0) return false;
        return S_ISDIR(information->st_mode) &&
                information->st_uid == kRadioUid && information->st_gid == kRadioGid &&
                Permissions(*information) == kDirectoryMode;
    }

    void State(const std::string& state) {
        // Report a state change once; this never alters producer/client logs.
        if (state != lastState_) {
            Log(false, "%s directory=%s", state.c_str(), directory_.c_str());
            lastState_ = state;
        }
    }

    bool Attach() {
        Fd candidate;
        struct stat information {};
        if (!OpenDirectory(&candidate, &information)) {
            State("directory-unavailable-or-rejected");
            return false;
        }
        inotifyFd_.reset(inotify_init1(IN_NONBLOCK | IN_CLOEXEC));
        if (!inotifyFd_.valid()) {
            State("inotify-init-failed");
            return false;
        }
        // Follow this process's magic FD link to the pinned directory inode.
        // No watch on /dev/socket and no external process /proc access.
        const int watch = inotify_add_watch(inotifyFd_.get(),
            ProcFd(candidate.get()).c_str(), kMask);
        if (watch < 0) {
            Log(true, "watch-attach-failed errno=%d", errno);
            inotifyFd_.reset();
            return false;
        }
        directoryFd_.reset(dup(candidate.get()));
        if (!directoryFd_.valid()) {
            Log(true, "directory-dup-failed errno=%d", errno);
            inotifyFd_.reset();
            return false;
        }
        // dup does not inherit CLOEXEC; the daemon never execs, but set it anyway.
        if (fcntl(directoryFd_.get(), F_SETFD, FD_CLOEXEC) < 0) {
            Log(true, "directory-cloexec-failed errno=%d", errno);
            Detach("directory-cloexec-failed");
            return false;
        }
        directoryIdentity_ = information;
        watch_ = watch;
        if (!IsCurrentDirectory()) {
            Detach("directory-changed-during-attach");
            return false;
        }
        State("watch-attached");
        Log(false, "watch-inode dev=%llu ino=%llu",
            static_cast<unsigned long long>(information.st_dev),
            static_cast<unsigned long long>(information.st_ino));
        return true;
    }

    void Detach(const char* reason) {
        if (directoryFd_.valid() || inotifyFd_.valid()) Log(false, "detach reason=%s", reason);
        // Recreate the entire instance after losing a watch. Old IN_IGNORED
        // records can therefore never be mistaken for a new reused watch ID.
        inotifyFd_.reset();
        directoryFd_.reset();
        watch_ = -1;
        rejected_.fill("");
        lastState_.clear();
    }

    bool IsCurrentDirectory() {
        if (!directoryFd_.valid()) return false;
        Fd current;
        struct stat information {};
        return OpenDirectory(&current, &information) &&
                SameInode(information, directoryIdentity_);
    }

    bool DrainEvents() {
        alignas(struct inotify_event) char buffer[16384];
        // Bound each drain so a sustained unrelated event storm cannot starve
        // endpoint rescans or SIGTERM handling indefinitely.
        for (unsigned batch = 0; batch < 16 && !gStop; ++batch) {
            const ssize_t count = read(inotifyFd_.get(), buffer, sizeof(buffer));
            if (count < 0) {
                if (errno == EINTR) continue;
                if (errno == EAGAIN || errno == EWOULDBLOCK) return true;
                Log(true, "inotify-read-failed errno=%d", errno);
                return false;
            }
            if (count == 0) return false;
            size_t offset = 0;
            while (offset < static_cast<size_t>(count)) {
                if (static_cast<size_t>(count) - offset < sizeof(struct inotify_event)) return false;
                const auto* event = reinterpret_cast<const struct inotify_event*>(buffer + offset);
                const size_t bytes = sizeof(*event) + event->len;
                if (bytes > static_cast<size_t>(count) - offset) return false;
                if (event->mask & IN_Q_OVERFLOW) {
                    Log(true, "queue-overflow rescan=both-fixed-endpoints");
                    // A complete scan follows the drain, even if the creation
                    // event for a target endpoint was dropped from this queue.
                } else if (event->wd != watch_) {
                    Log(true, "unexpected-watch-id");
                    return false;
                } else if (event->mask & (IN_IGNORED | IN_DELETE_SELF | IN_MOVE_SELF | IN_UNMOUNT)) {
                    return false;
                }
                offset += bytes;
            }
        }
        return true;
    }

    void Reject(size_t slot, const struct stat& information, const char* reason) {
        const std::string identity = std::to_string(information.st_dev) + ":" +
                std::to_string(information.st_ino) + ":" +
                std::to_string(information.st_uid) + ":" +
                std::to_string(information.st_gid) + ":" +
                std::to_string(information.st_mode) + ":" + reason;
        if (rejected_[slot] == identity) return;
        rejected_[slot] = identity;
        Log(true, "reject name=%s reason=%s uid=%u gid=%u mode=%04o ino=%llu",
            kNames[slot], reason, static_cast<unsigned>(information.st_uid),
            static_cast<unsigned>(information.st_gid),
            static_cast<unsigned>(Permissions(information)),
            static_cast<unsigned long long>(information.st_ino));
    }

    void Scan() {
        for (size_t slot = 0; slot < kNames.size(); ++slot) {
            if (gStop || !IsCurrentDirectory()) return;
            Repair(slot);
        }
    }

    void Repair(size_t slot) {
        const char* name = kNames[slot];
        Fd endpoint(openat(directoryFd_.get(), name, O_PATH | O_NOFOLLOW | O_CLOEXEC));
        if (!endpoint.valid()) {
            if (errno != ENOENT) Log(true, "endpoint-open-failed name=%s errno=%d", name, errno);
            rejected_[slot].clear();
            return;
        }
        struct stat before {};
        if (fstat(endpoint.get(), &before) != 0) {
            Log(true, "endpoint-stat-failed name=%s errno=%d", name, errno);
            return;
        }
        if (!S_ISSOCK(before.st_mode)) return Reject(slot, before, "not-socket");
        if (before.st_uid != kRadioUid || before.st_gid != kRadioGid) {
            return Reject(slot, before, "not-radio-owner-and-group");
        }
        if (Permissions(before) == kDesiredMode) {
            rejected_[slot].clear();
            return;
        }
        if (Permissions(before) != kExpectedMode) return Reject(slot, before, "unexpected-mode");
        struct stat named {};
        if (fstatat(directoryFd_.get(), name, &named, AT_SYMLINK_NOFOLLOW) != 0 ||
                !SameInode(before, named) || !IsCurrentDirectory()) return;
        const mode_t desired = Permissions(before) | S_IWGRP;
        // chmod on the magic link operates on the pinned O_PATH inode. It does
        // not follow a replacement pathname/symlink after the identity check.
        // fchmod(O_PATH_fd) is not used; it fails on Linux. No fchmodat2 needed.
        if (chmod(ProcFd(endpoint.get()).c_str(), desired) != 0) {
            Log(true, "permission-change-failed name=%s errno=%d", name, errno);
            return;
        }
        struct stat after {};
        if (fstat(endpoint.get(), &after) != 0 || !SameInode(before, after) ||
                !S_ISSOCK(after.st_mode) || after.st_uid != before.st_uid ||
                after.st_gid != before.st_gid || Permissions(after) != desired) {
            Log(true, "permission-readback-failed name=%s", name);
            return;
        }
        rejected_[slot].clear();
        if (fstatat(directoryFd_.get(), name, &named, AT_SYMLINK_NOFOLLOW) != 0 ||
                !SameInode(after, named) || !IsCurrentDirectory()) {
            Log(false, "repair-retired-inode name=%s current-path-will-be-rescanned", name);
            return;
        }
        Log(false, "repair-ok name=%s from=0700 to=0720 uid=1001 gid=1001 ino=%llu",
            name, static_cast<unsigned long long>(after.st_ino));
    }

    std::string directory_;
    Fd directoryFd_;
    Fd inotifyFd_;
    int watch_ = -1;
    struct stat directoryIdentity_ {};
    std::array<std::string, 2> rejected_;
    std::string lastState_;
};
}  // namespace

int main(int argc, char** argv) {
    std::string directory = kDirectory;
#if defined(KLEE_SOCKET_WATCHER_TESTING)
    if (argc != 3 || strcmp(argv[1], "--directory") != 0 || argv[2][0] != '/') {
        fprintf(stderr, "test build requires --directory /absolute/test/path\n");
        return 2;
    }
    directory = argv[2];
#else
    (void)argv;
    if (argc != 1) return 2;
#endif
    if (getuid() != kRadioUid || geteuid() != kRadioUid ||
            getgid() != kRadioGid || getegid() != kRadioGid) {
        Log(true, "refusing-unexpected-identity expected=1001:1001");
        return 2;
    }
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) {
        Log(true, "no-new-privileges-failed errno=%d", errno);
        return 2;
    }
    struct sigaction action {};
    action.sa_handler = Stop;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGTERM, &action, nullptr) != 0 ||
            sigaction(SIGINT, &action, nullptr) != 0) return 2;
    return Watcher(directory).Run();
}
