#!/usr/bin/env python3
"""CT-0427-64 KB binary local delete after CT-61 R2 mirror verification.

Reads manifest, for each entry deletes local_path (only if r2_url present
and file exists locally). Logs every delete to KB_BINARY_LOCAL_DELETE_LOG.txt.
"""
import json
import os
import sys
import time


def main(argv):
    if len(argv) < 2:
        print("usage: ct_0427_64_delete_locals.py <manifest.json> <delete_log.txt>",
              file=sys.stderr)
        return 2

    manifest_path, log_path = argv[0], argv[1]
    with open(manifest_path) as f:
        manifest = json.load(f)

    deleted = 0
    skipped_missing = 0
    skipped_no_r2 = 0
    bytes_freed = 0
    errors = []

    with open(log_path, "w") as logf:
        logf.write(f"# CT-0427-64 KB local delete log\n")
        logf.write(f"# Started: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
        logf.write(f"# Manifest: {manifest_path}\n")
        logf.write(f"# Total entries: {manifest['total_files']}\n\n")

        for entry in manifest["files"]:
            local = entry.get("local_path", "")
            r2_url = entry.get("r2_url", "")
            size = entry.get("size_bytes", 0)

            if not r2_url:
                logf.write(f"SKIP_NO_R2\t{local}\n")
                skipped_no_r2 += 1
                continue

            if not os.path.exists(local):
                logf.write(f"SKIP_MISSING\t{local}\n")
                skipped_missing += 1
                continue

            try:
                os.unlink(local)
                logf.write(f"DELETED\t{size}\t{local}\n")
                deleted += 1
                bytes_freed += size
            except OSError as e:
                logf.write(f"ERROR\t{e}\t{local}\n")
                errors.append((local, str(e)))

        logf.write(f"\n# === SUMMARY ===\n")
        logf.write(f"# Deleted: {deleted}\n")
        logf.write(f"# Bytes freed: {bytes_freed:,} ({bytes_freed/1024/1024/1024:.2f} GiB)\n")
        logf.write(f"# Skipped (missing locally): {skipped_missing}\n")
        logf.write(f"# Skipped (no R2 url): {skipped_no_r2}\n")
        logf.write(f"# Errors: {len(errors)}\n")
        logf.write(f"# Finished: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")

    print(f"deleted: {deleted}")
    print(f"bytes_freed: {bytes_freed:,} ({bytes_freed/1024/1024/1024:.2f} GiB)")
    print(f"skipped_missing: {skipped_missing}")
    print(f"skipped_no_r2: {skipped_no_r2}")
    print(f"errors: {len(errors)}")
    if errors:
        print("first 5 errors:")
        for path, msg in errors[:5]:
            print(f"  {path}: {msg}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
