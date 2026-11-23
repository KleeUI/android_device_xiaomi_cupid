// SPDX-License-Identifier: Apache-2.0
// One read-only diagnostic. Source only: not built, deployed or executed here.
// UAPI comes from the actual build's <linux/media.h>, never copied definitions.
// Device open allowlist: /dev/media0 and /dev/media1, read-only, once each.
// Ioctl allowlist: MEDIA_IOC_DEVICE_INFO and MEDIA_IOC_ENUM_ENTITIES only.
// No subdevice open/stat/access; no CAM_*/VIDIOC_* ioctl, exec, property or file write.
// JSONL stdout is measurement evidence, never a hardware-readiness qualification.

#define _GNU_SOURCE
#include <linux/media.h>
#include <sys/ioctl.h>
#include <fcntl.h>
#include <unistd.h>

#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

enum { MAX_ENTITIES = 256 };

/* Preserve arbitrary returned bytes as JSON escapes; no unbounded C strings. */
static void json_bytes_string(const char *value, size_t size) {
    putchar('"');
    for (size_t i = 0; i < size && value[i] != '\0'; ++i) {
        const unsigned char c = (unsigned char)value[i];
        if (c == '"' || c == '\\') {
            putchar('\\');
            putchar((int)c);
        } else if (c >= 0x20 && c <= 0x7e) {
            putchar((int)c);
        } else {
            printf("\\u%04x", (unsigned)c);
        }
    }
    putchar('"');
}

static void json_hex(const void *data, size_t size) {
    static const char digits[] = "0123456789abcdef";
    const unsigned char *bytes = (const unsigned char *)data;
    putchar('"');
    for (size_t i = 0; i < size; ++i) {
        putchar(digits[bytes[i] >> 4]);
        putchar(digits[bytes[i] & 15]);
    }
    putchar('"');
}

static void path_field(const char *path) {
    printf("\"path\":");
    json_bytes_string(path, strlen(path));
}

static void emit_info(const char *path, int rc, int saved_errno,
                      const struct media_device_info *info) {
    printf("{\"event\":\"device_info\",");
    path_field(path);
    printf(",\"rc\":%d,\"errno\":%d,\"buffer_valid\":%s,\"driver\":",
           rc, saved_errno, rc == 0 ? "true" : "false");
    json_bytes_string(info->driver, sizeof(info->driver));
    printf(",\"driver_hex\":");
    json_hex(info->driver, sizeof(info->driver));
    printf(",\"model\":");
    json_bytes_string(info->model, sizeof(info->model));
    printf(",\"model_hex\":");
    json_hex(info->model, sizeof(info->model));
    printf(",\"serial\":");
    json_bytes_string(info->serial, sizeof(info->serial));
    printf(",\"serial_hex\":");
    json_hex(info->serial, sizeof(info->serial));
    printf(",\"bus_info\":");
    json_bytes_string(info->bus_info, sizeof(info->bus_info));
    printf(",\"bus_info_hex\":");
    json_hex(info->bus_info, sizeof(info->bus_info));
    printf(",\"media_version\":%" PRIu32 ",\"hw_revision\":%" PRIu32
           ",\"driver_version\":%" PRIu32 "}\n",
           (uint32_t)info->media_version, (uint32_t)info->hw_revision,
           (uint32_t)info->driver_version);
}

static void emit_entity(const char *path, unsigned ordinal, uint32_t requested_id,
                        int rc, int saved_errno,
                        const struct media_entity_desc *entity) {
    printf("{\"event\":\"enum_call\",");
    path_field(path);
    printf(",\"ordinal\":%u,\"requested_id\":%" PRIu32
           ",\"rc\":%d,\"errno\":%d,\"buffer_valid\":%s,\"id\":%" PRIu32
           ",\"name\":",
           ordinal, requested_id, rc, saved_errno, rc == 0 ? "true" : "false",
           (uint32_t)entity->id);
    json_bytes_string(entity->name, sizeof(entity->name));
    printf(",\"name_hex\":");
    json_hex(entity->name, sizeof(entity->name));
    printf(",\"name_nul_terminated\":%s,\"type\":%" PRIu32
           ",\"group_id\":%" PRIu32 ",\"revision\":%" PRIu32
           ",\"flags\":%" PRIu32 ",\"pads\":%u,\"links\":%u"
           ",\"dev_major_raw_union\":%" PRIu32
           ",\"dev_minor_raw_union\":%" PRIu32 ",\"union_raw_hex\":",
           memchr(entity->name, '\0', sizeof(entity->name)) != NULL ? "true" : "false",
           (uint32_t)entity->type, (uint32_t)entity->group_id,
           (uint32_t)entity->revision, (uint32_t)entity->flags,
           (unsigned)entity->pads, (unsigned)entity->links,
           (uint32_t)entity->dev.major, (uint32_t)entity->dev.minor);
    json_hex(entity->raw, sizeof(entity->raw));
    printf("}\n");
}

static int inspect_one(const char *path) {
    errno = 0;
    /* Fixed literal allowlist supplied only by main; no path from CLI or graph. */
    const int fd = open(path, O_RDONLY | O_CLOEXEC);
    const int open_errno = fd < 0 ? errno : 0;
    printf("{\"event\":\"open\",");
    path_field(path);
    printf(",\"rc\":%d,\"errno\":%d,\"read_only\":true,\"cloexec\":true}\n",
           fd, open_errno);
    if (fd < 0) return 1;

    struct media_device_info info;
    memset(&info, 0, sizeof(info));
    errno = 0;
    int rc = ioctl(fd, MEDIA_IOC_DEVICE_INFO, &info);  /* whitelist operation 1 */
    int saved_errno = rc < 0 ? errno : 0;
    emit_info(path, rc, saved_errno, &info);

    int result = 0;
    unsigned entities = 0;
    bool ended = false;
    bool ended_with_einval = false;
    const char *reason = "device-info-failed";
    if (rc != 0) {
        result = 1;  /* No enum or other fallback after unexpected info result. */
    } else {
        uint32_t cursor = 0;
        for (unsigned ordinal = 0; ordinal < MAX_ENTITIES; ++ordinal) {
            struct media_entity_desc entity;
            memset(&entity, 0, sizeof(entity));
            const uint32_t requested_id = cursor | MEDIA_ENT_ID_FLAG_NEXT;
            entity.id = requested_id;
            errno = 0;
            rc = ioctl(fd, MEDIA_IOC_ENUM_ENTITIES, &entity);  /* whitelist operation 2 */
            saved_errno = rc < 0 ? errno : 0;
            emit_entity(path, ordinal, requested_id, rc, saved_errno, &entity);
            if (rc != 0) {
                ended = true;
                ended_with_einval = rc < 0 && saved_errno == EINVAL;
                reason = ended_with_einval ? "einval-end-of-current-enumeration"
                                          : "enum-call-failed-no-retry";
                if (!ended_with_einval) result = 1;
                break;
            }
            ++entities;
            if (entity.id == 0 || entity.id <= cursor ||
                (entity.id & MEDIA_ENT_ID_FLAG_NEXT) != 0) {
                reason = "invalid-or-nonincreasing-entity-id";
                result = 1;
                break;
            }
            cursor = entity.id;
            reason = "entity-limit-without-observed-end";
        }
        if (!ended) result = 1;  /* Includes cap and malformed ID; never call again. */
    }

    printf("{\"event\":\"enumeration_summary\",");
    path_field(path);
    printf(",\"entities_returned\":%u,\"entity_limit\":%u"
           ",\"end_observed\":%s,\"ended_with_einval\":%s,\"empty\":%s"
           ",\"hardware_readiness_verified\":false,\"reason\":",
           entities, (unsigned)MAX_ENTITIES, ended ? "true" : "false",
           ended_with_einval ? "true" : "false", entities == 0 ? "true" : "false");
    json_bytes_string(reason, strlen(reason));
    printf("}\n");

    errno = 0;
    const int close_rc = close(fd);  /* No retry; do not accidentally close reused fd. */
    const int close_errno = close_rc < 0 ? errno : 0;
    printf("{\"event\":\"close\",");
    path_field(path);
    printf(",\"rc\":%d,\"errno\":%d}\n", close_rc, close_errno);
    if (close_rc != 0) result = 1;
    return result;
}

int main(void) {
    /* Emit compile-time ABI facts, never guessed hardcoded struct sizes. */
    setvbuf(stdout, NULL, _IONBF, 0);
    printf("{\"event\":\"start\",\"schema\":\"klee-media-enumeration-probe-v1\""
           ",\"sizeof_media_device_info\":%zu,\"sizeof_media_entity_desc\":%zu"
           ",\"media_ioc_device_info\":%lu,\"media_ioc_enum_entities\":%lu"
           ",\"next_flag\":%" PRIu32 ",\"max_devices\":2,\"max_entities_per_device\":%u"
           ",\"device_write_requested\":false,\"subdevice_open_requested\":false"
           ",\"querycap_requested\":false,\"automatic_retry\":false}\n",
           sizeof(struct media_device_info), sizeof(struct media_entity_desc),
           (unsigned long)MEDIA_IOC_DEVICE_INFO, (unsigned long)MEDIA_IOC_ENUM_ENTITIES,
           (uint32_t)MEDIA_ENT_ID_FLAG_NEXT, (unsigned)MAX_ENTITIES);
    int failures = inspect_one("/dev/media0");
    failures += inspect_one("/dev/media1");
    const int stream_failed = ferror(stdout) != 0;
    const int exit_code = failures != 0 || stream_failed ? 2 : 0;
    printf("{\"event\":\"result\",\"devices_attempted\":2,\"device_failures\":%d"
           ",\"stdout_error_before_result\":%s,\"hardware_readiness_verified\":false"
           ",\"exit_code\":%d}\n", failures, stream_failed ? "true" : "false", exit_code);
    return ferror(stdout) != 0 ? 2 : exit_code;
}
