// SPDX-License-Identifier: Apache-2.0
// Readiness publisher candidate. Same core is used by target and host fixtures.
#pragma once
#include <algorithm>
#include <cerrno>
#include <cstdint>
#include <map>
#include <set>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

namespace klee_camera {
constexpr const char kReadyProperty[] = "vendor.klee.camera.ready";
constexpr const char kReadyValue[] = "1";
constexpr uint32_t kNext = UINT32_C(1) << 31;
constexpr unsigned kMediaSlots = 32;  // Search bound, never a selected media number.
constexpr unsigned kMaxEntities = 256;
constexpr int64_t kBudgetMs = 15000;
constexpr int64_t kPollMs = 100;

// Current kernel cam_req_mgr.h: CAM_DEVICE_TYPE_BASE = MEDIA_ENT_F_OLD_BASE.
// SHA256 8bedba64c98bf329adca74e869766e4dddc113f399e2fb821c0a7b6463284168.
// These are Qualcomm function values, NOT generic MEDIA_ENT_F_* classifications.
constexpr uint32_t kBase = 0x10000;
constexpr uint32_t kVideo = kBase, kSensor = kBase + 1, kIfe = kBase + 2;
constexpr uint32_t kIcp = kBase + 3, kJpeg = kBase + 5, kCpas = kBase + 7;
constexpr uint32_t kCsiphy = kBase + 8, kActuator = kBase + 9, kCci = kBase + 10;
constexpr uint32_t kFlash = kBase + 11, kEeprom = kBase + 12;
constexpr uint32_t kOis = kBase + 13, kTpg = kBase + 18;

template<class T> struct Call { T value{}; int error = 0; };
enum class State { Complete, Pending, Permanent, TimedOut };
struct Verdict {
    State state;
    std::string reason;
    int error = 0;
};
inline Verdict Complete() { return {State::Complete, "complete", 0}; }
inline Verdict Pending(const std::string& why, int e = 0) { return {State::Pending, why, e}; }
inline Verdict Fail(const std::string& why, int e = 0) { return {State::Permanent, why, e}; }
inline Verdict Timeout() { return {State::TimedOut, "monotonic-deadline-exhausted", ETIMEDOUT}; }
inline bool Good(const Verdict& v) { return v.state == State::Complete; }

struct Identity {
    uint32_t uid = 0, euid = 0, suid = 0, gid = 0, egid = 0, sgid = 0;
    std::vector<uint32_t> groups;
};
struct Node {
    bool character = false;
    uint64_t filesystem = 0, inode = 0;
    uint32_t major = 0, minor = 0, mode = 0, uid = 0, gid = 0;
    auto Key() const { return std::tie(character, filesystem, inode, major, minor, mode, uid, gid); }
    bool operator==(const Node& o) const { return Key() == o.Key(); }
};
struct Info {
    std::string driver, model, serial, bus;
    uint32_t media_version = 0, driver_version = 0, hardware_revision = 0;
    auto Key() const { return std::tie(driver, model, serial, bus, media_version, driver_version, hardware_revision); }
    bool operator==(const Info& o) const { return Key() == o.Key(); }
};
struct Entity {
    uint32_t id = 0, type = 0, group = 0, revision = 0, flags = 0;
    uint16_t pads = 0, links = 0;
    std::string name;
    uint32_t major = 0, minor = 0;
    auto Key() const { return std::tie(id, type, group, revision, flags, pads, links, name, major, minor); }
    bool operator==(const Entity& o) const { return Key() == o.Key(); }
};
struct LocatedNode {
    std::string path;
    Node node;
    bool operator==(const LocatedNode& o) const { return path == o.path && node == o.node; }
};
struct Graph {
    std::string path;
    Node media_node;
    Info info;
    std::vector<Entity> entities;
    std::vector<LocatedNode> nodes;
    bool operator==(const Graph& o) const {
        return path == o.path && media_node == o.media_node && info == o.info &&
               entities == o.entities && nodes == o.nodes;
    }
};
struct Snapshot {
    Graph request, sync;
    bool operator==(const Snapshot& o) const { return request == o.request && sync == o.sync; }
};

// Only these operations exist: media-node reads and one fixed readiness property.
// No subdevice/video open, device write, credential/capability/domain mutation,
// fork/exec, Binder, link setup, CAM/VIDIOC or hardware acquisition operation.
class Api {
public:
    virtual ~Api() = default;
    virtual int64_t NowMs() = 0;  // -1 means clock failure; monotonic clock only.
    virtual int SleepUntilMs(int64_t until) = 0;
    virtual Call<Identity> IdentityNow() = 0;
    virtual Call<Node> Lstat(const std::string& path) = 0;
    virtual Call<int> OpenMedia(const std::string& path) = 0;
    virtual Call<Node> Fstat(int fd) = 0;
    virtual Call<Info> DeviceInfo(int fd) = 0;
    virtual Call<Entity> EnumNext(int fd, uint32_t requested) = 0;
    virtual int Close(int fd) = 0;  // Exactly once; never retry close(EINTR).
    virtual int PublishReady() = 0;  // Fixed key/value only; error number, zero on success.
    virtual void Log(const Verdict& v) = 0;
};

inline bool Expired(Api& a, int64_t end) {
    const int64_t now = a.NowMs();
    return now < 0 || now >= end;
}
// Preserve successful resource-returning calls even if time expires during them:
// their caller must close that FD. Never replace a successful open with timeout.
template<class F> auto RetryInterrupted(Api& a, int64_t end, F operation) -> decltype(operation()) {
    for (;;) {
        if (Expired(a, end)) return {{}, ETIMEDOUT};
        auto r = operation();
        if (r.error != EINTR) return r;
    }
}
inline Verdict Error(const std::string& stage, int e) {
    if (e == ETIMEDOUT) return Timeout();
    if (e == ENOENT || e == ENODEV) return Pending(stage, e);
    return Fail(stage, e);  // Includes stable EACCES/EPERM/ENOTTY, never masked.
}
inline Identity ExpectedIdentity() {
    return {1047, 1047, 1047, 1005, 1005, 1005, {1004, 1006, 1026, 2907}};
}
// POSIX mode-bit calculation only: does not assert SELinux permission, ACL state,
// file capabilities, or a future process's access. Exact published mode/ownership
// and the fixed numeric provider identity are separate mandatory checks below.
inline bool ModeAllowsReadWrite(const Node& node, const Identity& identity) {
    unsigned shift = 0;
    if (identity.euid == node.uid) shift = 6;
    else if (identity.egid == node.gid ||
             std::find(identity.groups.begin(), identity.groups.end(), node.gid) != identity.groups.end())
        shift = 3;
    return ((node.mode >> shift) & 06u) == 06u;
}
inline Verdict IdentityCheck(Api& a, int64_t end) {
    auto r = RetryInterrupted(a, end, [&] { return a.IdentityNow(); });
    if (r.error) return Error("helper-identity-read", r.error);
    auto& i = r.value;
    std::sort(i.groups.begin(), i.groups.end());
    const Identity expected = ExpectedIdentity();
    if (i.uid != expected.uid || i.euid != expected.euid || i.suid != expected.suid ||
        i.gid != expected.gid || i.egid != expected.egid || i.sgid != expected.sgid ||
        i.groups != expected.groups)
        return Fail("not-fixed-provider-numeric-identity");
    return Complete();
}

inline bool Numbered(const std::string& s, const std::string& prefix) {
    if (s.size() <= prefix.size() || s.compare(0, prefix.size(), prefix) != 0) return false;
    const std::string n = s.substr(prefix.size());
    if (n.size() > 4 || (n.size() > 1 && n[0] == '0')) return false;
    return std::all_of(n.begin(), n.end(), [](char c) { return c >= '0' && c <= '9'; });
}
inline Verdict CheckNode(Api& a, int64_t end, const std::string& path,
                         uint32_t major, uint32_t minor, Node* out) {
    auto first = RetryInterrupted(a, end, [&] { return a.Lstat(path); });
    if (first.error) return Error("node-lstat-before:" + path, first.error);
    if (!first.value.character) return Fail("node-not-character-or-is-symlink:" + path);
    if (first.value.major != major || first.value.minor != minor)
        return Pending("node-rdev-not-published:" + path);
    if (first.value.mode != 0660 || first.value.uid != 1000 || first.value.gid != 1006)
        return Pending("node-dac-not-published:" + path);
    if (!ModeAllowsReadWrite(first.value, ExpectedIdentity()))
        return Fail("published-node-mode-denies-fixed-provider-identity:" + path);
    auto last = RetryInterrupted(a, end, [&] { return a.Lstat(path); });
    if (last.error) return Error("node-lstat-after:" + path, last.error);
    if (!(first.value == last.value)) return Pending("node-changed-during-check:" + path);
    *out = last.value;
    return Complete();
}

inline const std::map<uint32_t, unsigned>& RequestRoster() {
    static const std::map<uint32_t, unsigned> roster = {
        {kVideo, 1}, {kSensor, 4}, {kIfe, 1}, {kIcp, 1}, {kJpeg, 1},
        {kCpas, 1}, {kCsiphy, 6}, {kActuator, 2}, {kCci, 2},
        {kFlash, 3}, {kEeprom, 4}, {kOis, 1}, {kTpg, 3}};
    return roster;
}
inline Verdict ValidateGraph(Api& a, int64_t end, bool sync, Graph* graph) {
    const std::map<uint32_t, unsigned> expected = sync ?
        std::map<uint32_t, unsigned>{{kVideo, 1}} : RequestRoster();
    std::map<uint32_t, unsigned> actual;
    std::set<std::pair<uint32_t, uint32_t>> devices;
    std::set<std::string> paths;
    for (const auto& e : graph->entities) {
        if (!expected.count(e.type)) return Fail("unexpected-camera-entity-type");
        if (e.group || e.revision || e.flags || e.pads || e.links)
            return Fail("unexpected-camera-entity-metadata");
        if (++actual[e.type] > expected.at(e.type)) return Fail("excess-camera-entity-type");
        if (e.type == kCci) {
            // cam_cci_dev.c: HAS_EVENTS only, no HAS_DEVNODE, function=CCI.
            if (e.name != "cam-cci-driver" || e.major || e.minor)
                return Fail("cci-nondevnode-contract-mismatch");
            continue;
        }
        const bool video = e.type == kVideo;
        const std::string prefix = video ? "video" : "v4l-subdev";
        // Registration precedes devnode assignment AND entity rename. Such a
        // partial publication is pending, never a successful complete graph.
        if (!Numbered(e.name, prefix) || e.major == 0)
            return Pending("camera-entity-node-publication-incomplete:" + graph->path + ":" + e.name);
        if (!devices.insert({e.major, e.minor}).second)
            return Fail("duplicate-camera-rdev");
        const std::string path = "/dev/" + e.name;
        if (!paths.insert(path).second) return Fail("duplicate-camera-node-name");
        Node node;
        auto v = CheckNode(a, end, path, e.major, e.minor, &node);
        if (!Good(v)) return v;
        graph->nodes.push_back({path, node});
    }
    if (actual != expected) {
        std::string detail = "required-type-roster-incomplete:" + graph->path;
        for (const auto& wanted : expected) {
            const unsigned count = actual.count(wanted.first) ? actual.at(wanted.first) : 0;
            if (count < wanted.second) detail += ":type=" + std::to_string(wanted.first) +
                ",have=" + std::to_string(count) + ",need=" + std::to_string(wanted.second);
        }
        return Pending(detail);
    }
    std::sort(graph->nodes.begin(), graph->nodes.end(), [](const auto& x, const auto& y) {
        return x.path < y.path;
    });
    return Complete();
}

inline Verdict ReadGraph(Api& a, int64_t end, const std::string& path,
                         const Node& before, Graph* graph, int* role) {
    *role = 0;
    auto opened = RetryInterrupted(a, end, [&] { return a.OpenMedia(path); });
    if (opened.error) {
        if (opened.error == EACCES && (before.mode != 0660 || before.uid != 1000 || before.gid != 1006))
            return Pending("media-open-awaiting-dac:" + path, opened.error);
        return Error("media-open:" + path, opened.error);
    }
    const int fd = opened.value;
    // Every path after a successful open reaches this single close call.
    const auto inspect = [&]() -> Verdict {
        auto fdstat = RetryInterrupted(a, end, [&] { return a.Fstat(fd); });
        if (fdstat.error) return Error("media-fstat", fdstat.error);
        if (!(fdstat.value == before)) return Pending("media-node-replaced-during-open");
        auto info = RetryInterrupted(a, end, [&] { return a.DeviceInfo(fd); });
        if (info.error) return Error("media-device-info", info.error);
        if (info.value.driver == "cam_req_mgr" && info.value.model == "cam-req-mgr-devnode") *role = 1;
        else if (info.value.driver == "cam_sync" && info.value.model == "cam_sync_device") *role = 2;
        else return Complete();  // An unrelated graph is never a ready substitute.
        Node verified;
        auto access = CheckNode(a, end, path, before.major, before.minor, &verified);
        if (!Good(access)) return access;
        if (!(verified == before)) return Pending("selected-media-node-changed:" + path);
        graph->path = path;
        graph->media_node = before;
        graph->info = info.value;
        uint32_t cursor = 0;
        bool ended = false;
        for (unsigned n = 0; n < kMaxEntities; ++n) {
            auto e = RetryInterrupted(a, end, [&] { return a.EnumNext(fd, cursor | kNext); });
            if (e.error == EINVAL) { ended = true; break; }
            if (e.error) return Error("media-enum", e.error);
            if (!e.value.id || e.value.id <= cursor || (e.value.id & kNext) ||
                e.value.name.empty() || e.value.name.size() >= 32)
                return Fail("malformed-or-nonincreasing-entity");
            cursor = e.value.id;
            graph->entities.push_back(e.value);  // Never use failed ioctl buffers.
        }
        if (!ended) return Fail("entity-limit-without-observed-end");
        auto last = RetryInterrupted(a, end, [&] { return a.Lstat(path); });
        if (last.error) return Error("media-lstat-after", last.error);
        if (!(last.value == before)) return Pending("media-node-changed-during-enumeration");
        return Complete();
    };
    Verdict v = inspect();
    const int closed = a.Close(fd);
    if (closed) return Fail("media-close-no-retry", closed);
    if (!Good(v) || *role == 0) return v;
    return ValidateGraph(a, end, *role == 2, graph);
}

inline Verdict ReadSnapshot(Api& a, int64_t end, Snapshot* snapshot) {
    unsigned requests = 0, syncs = 0;
    for (unsigned n = 0; n < kMediaSlots; ++n) {
        const std::string path = "/dev/media" + std::to_string(n);
        auto stat = RetryInterrupted(a, end, [&] { return a.Lstat(path); });
        if (stat.error == ENOENT) continue;
        if (stat.error) return Error("media-lstat-discovery", stat.error);
        if (!stat.value.character) return Fail("media-path-not-character-or-is-symlink");
        Graph graph;
        int role = 0;
        auto v = ReadGraph(a, end, path, stat.value, &graph, &role);
        if (!Good(v)) return v;
        if (role == 1) {
            if (++requests != 1) return Fail("multiple-request-manager-graphs");
            snapshot->request = std::move(graph);
        } else if (role == 2) {
            if (++syncs != 1) return Fail("multiple-sync-graphs");
            snapshot->sync = std::move(graph);
        }
    }
    if (requests != 1 || syncs != 1) return Pending("required-media-graph-not-present");
    for (const auto& x : snapshot->request.nodes) for (const auto& y : snapshot->sync.nodes) {
        if (x.path == y.path || (x.node.major == y.node.major && x.node.minor == y.node.minor))
            return Fail("request-and-sync-device-alias");
    }
    if (Expired(a, end)) return Timeout();
    return Complete();
}

// Publication is a single irreversible fixed-key operation after all media FDs
// close. Failed or timed-out graph checks never publish. Publish errors (including
// EINTR) are not retried because the service may already have accepted the write.
inline int RunAndPublish(Api& a) {
    const int64_t start = a.NowMs();
    if (start < 0) { a.Log(Fail("monotonic-clock-failed")); return 78; }
    const int64_t end = start + kBudgetMs;
    auto identity = IdentityCheck(a, end);
    if (!Good(identity)) { a.Log(identity); return identity.state == State::TimedOut ? 75 : 78; }
    a.Log(Pending("starting-readiness-budget-ms=15000-poll-ms=100"));
    Snapshot previous;
    bool have_previous = false;
    std::tuple<State, std::string, int> last_log{State::Complete, "", 0};
    auto changed_log = [&](const Verdict& v) {
        const auto key = std::make_tuple(v.state, v.reason, v.error);
        if (key != last_log) { a.Log(v); last_log = key; }
    };
    for (;;) {
        if (Expired(a, end)) { changed_log(Timeout()); return 75; }
        Snapshot now;
        auto v = ReadSnapshot(a, end, &now);
        if (Good(v)) {
            if (have_previous && now == previous) {
                // Final independent recheck closes the second-snapshot/publish gap
                // as far as sampling can. It cannot eliminate the final TOCTOU.
                Snapshot final;
                v = ReadSnapshot(a, end, &final);
                if (Good(v) && !(final == now)) v = Pending("graph-changed-before-publish");
                if (Good(v)) v = IdentityCheck(a, end);
                if (Good(v) && Expired(a, end)) v = Timeout();
                if (Good(v)) {
                    changed_log({State::Complete,
                        "stable-complete-graphs-publish-ready:req_entities=" +
                        std::to_string(final.request.entities.size()) + ":sync_entities=" +
                        std::to_string(final.sync.entities.size()) + ":samples=2+final1:req=" +
                        final.request.path + ":sync=" + final.sync.path, 0});
                    if (Expired(a, end)) { changed_log(Timeout()); return 75; }
                    const int e = a.PublishReady();
                    if (e) {
                        a.Log(Fail("readiness-property-attempt-failed-outcome-unknown-no-retry", e));
                        return 126;
                    }
                    // A successful property call cannot be rolled back, even if
                    // the syscall itself returned after the userspace budget.
                    a.Log({State::Complete, "fixed-readiness-property-published-once", 0});
                    return 0;
                }
                have_previous = false;
            } else {
                previous = std::move(now);
                have_previous = true;
                v = Pending("first-or-changed-complete-snapshot");
            }
        } else have_previous = false;
        changed_log(v);
        if (v.state == State::Permanent) return 78;
        if (v.state == State::TimedOut) return 75;
        const int64_t clock = a.NowMs();
        if (clock < 0 || clock >= end) { changed_log(Timeout()); return 75; }
        const int64_t wake = std::min(end, clock + kPollMs);
        for (;;) {
            if (Expired(a, end)) { changed_log(Timeout()); return 75; }
            const int e = a.SleepUntilMs(wake);
            if (e == EINTR) continue;
            if (e) { changed_log(Fail("monotonic-sleep-failed", e)); return 78; }
            break;
        }
    }
}
}  // namespace klee_camera
