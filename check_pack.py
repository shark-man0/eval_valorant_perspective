import os
import zipfile
import hashlib
from pathlib import Path

zip_path = Path(os.environ["ZIP_TO_CHECK"])
pack = Path(os.environ["PACK_TO_CHECK"])
prefix = "valorant_e2e_validation_pack_v3/"

def sha(data):
    return hashlib.sha256(data).hexdigest()

with zipfile.ZipFile(zip_path) as z:
    mismatches = []

    for name in z.namelist():
        if not name.startswith(prefix) or name.endswith("/"):
            continue

        rel = name[len(prefix):]

        if not (rel.endswith(".json") or rel.endswith(".py")):
            continue

        extracted = pack / rel

        if not extracted.exists():
            mismatches.append((rel, "MISSING"))
            continue

        zip_hash = sha(z.read(name))
        disk_hash = sha(extracted.read_bytes())

        if zip_hash != disk_hash:
            mismatches.append(
                (rel, f"{zip_hash} != {disk_hash}")
            )

    if not mismatches:
        print("ZIP and extracted pack are identical")
    else:
        print("MISMATCHED FILES:")
        for rel, reason in mismatches:
            print(rel)
            print(" ", reason)
