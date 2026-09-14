#define _GNU_SOURCE

#include <errno.h>
#include <stdio.h>
#include <string.h>

#if defined(__linux__)
#include <fcntl.h>
#include <sys/syscall.h>
#include <unistd.h>
#ifndef RENAME_NOREPLACE
#define RENAME_NOREPLACE (1U << 0)
#endif
#elif !defined(__APPLE__)
#error "rename-noreplace supports only Linux and macOS"
#endif

int main(int argc, char **argv) {
    int result;

    if (argc != 3) {
        fprintf(stderr, "usage: %s SOURCE DESTINATION\n", argv[0]);
        return 64;
    }

#if defined(__APPLE__)
    result = renamex_np(argv[1], argv[2], RENAME_EXCL);
#else
    result = (int)syscall(SYS_renameat2, AT_FDCWD, argv[1], AT_FDCWD, argv[2],
                          RENAME_NOREPLACE);
#endif

    if (result == 0) {
        return 0;
    }

    if (errno == EEXIST || errno == ENOTEMPTY) {
        fprintf(stderr, "destination exists: %s\n", argv[2]);
        return 73;
    }
    if (errno == ENOSYS || errno == EINVAL) {
        fprintf(stderr,
                "atomic rename-no-replace is unavailable on this filesystem: %s\n",
                argv[2]);
        return 69;
    }

    fprintf(stderr, "rename-no-replace %s -> %s: %s\n", argv[1], argv[2],
            strerror(errno));
    return 74;
}
