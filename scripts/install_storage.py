import hashlib
import json
import os
import platform
import shutil
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if platform.machine().lower() not in {"amd64", "x86_64"}:
        raise SystemExit("Storage installer currently supports amd64 Windows and Linux.")
    release = json.loads((ROOT / "infra/storage/seaweedfs-release.json").read_text())
    target = "windows" if os.name == "nt" else "linux"
    asset = release[target]
    directory = ROOT / ".local" / "bin"
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / asset["asset"]
    request = urllib.request.Request(
        f"https://github.com/seaweedfs/seaweedfs/releases/download/{release['version']}/{asset['asset']}",
        headers={"User-Agent": "HAPPY-foundation-installer"},
    )
    if not archive.exists():
        with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)
    with archive.open("rb") as downloaded:
        digest = hashlib.file_digest(downloaded, "sha256").hexdigest()
    if digest != asset["sha256"]:
        archive.unlink()
        raise SystemExit("Storage archive checksum mismatch; nothing was installed.")

    name = "weed.exe" if target == "windows" else "weed"
    destination = directory / name
    # Extract only the expected executable, never arbitrary archive paths.
    if target == "windows":
        with (
            zipfile.ZipFile(archive) as package,
            package.open(name) as source,
            destination.open("wb") as output,
        ):
            shutil.copyfileobj(source, output)
    else:
        with tarfile.open(archive) as package:
            source = package.extractfile(name)
            if source is None:
                raise SystemExit("Storage archive has no executable.")
            with source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)
        destination.chmod(0o755)
    print(f"Installed checksum-verified SeaweedFS {release['version']} in .local/bin.")


if __name__ == "__main__":
    main()
