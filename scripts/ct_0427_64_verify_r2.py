#!/usr/bin/env python3
"""CT-0427-64 pre-delete verification: sample 5 random files from manifest,
retrieve from R2, verify md5 + size match. Exit 0 only if all 5 pass.
Usage: python3 ct_0427_64_verify_r2.py <manifest.json>
"""
import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile


def main(argv):
    if len(argv) < 1:
        print("usage: ct_0427_64_verify_r2.py <manifest.json>", file=sys.stderr)
        return 2
    with open(argv[0]) as f:
        manifest = json.load(f)

    files = manifest["files"]
    samples = random.sample(files, min(5, len(files)))
    print(f"Sampling 5 of {manifest['total_files']} files for retrieval verification")
    print(f"Total mirror size: {manifest['total_bytes']/1024/1024/1024:.2f} GiB")
    print()

    passed = 0
    for i, s in enumerate(samples, 1):
        r2_url = s["r2_url"]
        expected_md5 = s.get("hashes", {}).get("md5", "")
        expected_size = s["size_bytes"]
        name = s["r2_path"][:80]
        print(f"[{i}/5] {name}")
        print(f"      expected: {expected_size} bytes, md5={expected_md5}")

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        try:
            r = subprocess.run(
                ["rclone", "copyto", r2_url, tmp_path],
                capture_output=True, text=True, timeout=300,
            )
            if r.returncode != 0:
                print(f"      FAIL: rclone exit {r.returncode}: {r.stderr[:200]}")
                continue

            actual_size = os.path.getsize(tmp_path)
            with open(tmp_path, "rb") as f:
                actual_md5 = hashlib.md5(f.read()).hexdigest()

            size_ok = actual_size == expected_size
            md5_ok = actual_md5 == expected_md5
            print(f"      actual:   {actual_size} bytes, md5={actual_md5}")
            if size_ok and md5_ok:
                print(f"      PASS")
                passed += 1
            else:
                print(f"      FAIL (size_ok={size_ok}, md5_ok={md5_ok})")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        print()

    print(f"=== RESULT: {passed}/5 verified ===")
    return 0 if passed == 5 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
