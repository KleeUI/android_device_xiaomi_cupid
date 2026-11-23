// SPDX-License-Identifier: Apache-2.0
// Readiness publisher candidate. Original HAL is started only by init.
#include "readiness_core.h"
#include <android/log.h>
#include <linux/media.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/system_properties.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>
#include <inttypes.h>
#include <cstring>

namespace kc = klee_camera;
namespace {
kc::Node NodeFrom(const struct stat& s) {
    return {S_ISCHR(s.st_mode), static_cast<uint64_t>(s.st_dev),
            static_cast<uint64_t>(s.st_ino), static_cast<uint32_t>(major(s.st_rdev)),
            static_cast<uint32_t>(minor(s.st_rdev)), static_cast<uint32_t>(s.st_mode & 07777),
            static_cast<uint32_t>(s.st_uid), static_cast<uint32_t>(s.st_gid)};
}
template<size_t N> bool Bounded(const char (&s)[N], std::string* out) {
    const size_t length = strnlen(s, N);
    if (length == N) return false;
    out->assign(s, length);
    return true;
}
class PosixApi final : public kc::Api {
    int64_t start_ms_ = 0;
    std::string identity_summary_ = "identity=unread";
public:
    PosixApi() { start_ms_ = NowMs(); }
    int64_t NowMs() override {
        struct timespec ts{};
        if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) return -1;
        return static_cast<int64_t>(ts.tv_sec) * 1000 + ts.tv_nsec / 1000000;
    }
    int SleepUntilMs(int64_t until) override {
        struct timespec ts{static_cast<time_t>(until / 1000),
                           static_cast<long>((until % 1000) * 1000000)};
        // clock_nanosleep returns an error number directly, not errno.
        return clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &ts, nullptr);
    }
    kc::Call<kc::Identity> IdentityNow() override {
        uid_t r = 0, e = 0, s = 0;
        gid_t gr = 0, ge = 0, gs = 0;
        if (getresuid(&r, &e, &s) != 0 || getresgid(&gr, &ge, &gs) != 0)
            return {{}, errno};
        const int count = getgroups(0, nullptr);
        if (count < 0) return {{}, errno};
        if (count > 64) return {{}, E2BIG};
        std::vector<gid_t> groups(static_cast<size_t>(count));
        if (getgroups(count, groups.data()) != count) return {{}, errno ? errno : EIO};
        kc::Identity result;
        result.uid = r; result.euid = e; result.suid = s;
        result.gid = gr; result.egid = ge; result.sgid = gs;
        for (gid_t group : groups) result.groups.push_back(static_cast<uint32_t>(group));
        identity_summary_ = "uid=" + std::to_string(result.uid) + "/" +
            std::to_string(result.euid) + "/" + std::to_string(result.suid) +
            " gid=" + std::to_string(result.gid) + "/" + std::to_string(result.egid) +
            "/" + std::to_string(result.sgid) + " groups=";
        for (const auto group : result.groups) identity_summary_ += std::to_string(group) + ",";
        return {result, 0};
    }
    kc::Call<kc::Node> Lstat(const std::string& path) override {
        struct stat s{};
        if (lstat(path.c_str(), &s) != 0) return {{}, errno};
        return {NodeFrom(s), 0};
    }
    kc::Call<int> OpenMedia(const std::string& path) override {
        // Only ReadSnapshot's bounded /dev/mediaN candidates reach this method.
        const int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
        return {fd, fd < 0 ? errno : 0};
    }
    kc::Call<kc::Node> Fstat(int fd) override {
        struct stat s{};
        if (fstat(fd, &s) != 0) return {{}, errno};
        return {NodeFrom(s), 0};
    }
    kc::Call<kc::Info> DeviceInfo(int fd) override {
        struct media_device_info info{};
        const int rc = ioctl(fd, MEDIA_IOC_DEVICE_INFO, &info);
        if (rc != 0) return {{}, rc < 0 ? errno : EPROTO};
        kc::Info out;
        if (!Bounded(info.driver, &out.driver) || !Bounded(info.model, &out.model) ||
            !Bounded(info.serial, &out.serial) || !Bounded(info.bus_info, &out.bus))
            return {{}, EPROTO};
        out.media_version = info.media_version;
        out.driver_version = info.driver_version;
        out.hardware_revision = info.hw_revision;
        return {out, 0};
    }
    kc::Call<kc::Entity> EnumNext(int fd, uint32_t requested) override {
        struct media_entity_desc entity{};
        entity.id = requested;
        const int rc = ioctl(fd, MEDIA_IOC_ENUM_ENTITIES, &entity);
        if (rc != 0) return {{}, rc < 0 ? errno : EPROTO};
        kc::Entity out;
        if (!Bounded(entity.name, &out.name)) return {{}, EPROTO};
        out.id = entity.id; out.type = entity.type; out.group = entity.group_id;
        out.revision = entity.revision; out.flags = entity.flags;
        out.pads = entity.pads; out.links = entity.links;
        // Store union bytes; only the pinned Qualcomm types interpret dev in core.
        out.major = entity.dev.major; out.minor = entity.dev.minor;
        return {out, 0};
    }
    int Close(int fd) override { return close(fd) == 0 ? 0 : errno; }
    int PublishReady() override {
        // The caller supplies neither property name nor value. No alternate
        // exec, control message, reset, persistent state, or publication retry.
        errno = 0;
        const int rc = __system_property_set(kc::kReadyProperty, kc::kReadyValue);
        return rc == 0 ? 0 : (errno ? errno : EIO);
    }
    void Log(const kc::Verdict& v) override {
        const int64_t now = NowMs();
        __android_log_buf_print(LOG_ID_SYSTEM,
            v.state == kc::State::Permanent ? ANDROID_LOG_ERROR : ANDROID_LOG_INFO,
            "klee.camera.ready", "monotonic_ms=%" PRId64 " elapsed_ms=%" PRId64
            " state=%d reason=%s errno=%d %s", now, now - start_ms_,
            static_cast<int>(v.state), v.reason.c_str(), v.error, identity_summary_.c_str());
    }
};
}  // namespace
int main(int argc, char**) {
    PosixApi api;
    if (argc != 1) {
        api.Log(kc::Fail("helper-accepts-no-arguments"));
        return 78;
    }
    return kc::RunAndPublish(api);
}
