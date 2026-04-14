#!/usr/bin/env python3
"""
download — download files from a URL list file.

Usage:
    python download.py urls.txt
    python download.py urls.txt -o downloads/ -w 4 -t 30
"""

import argparse
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def parse_url_file(path: str) -> list[str]:
    """Read URLs from a file, skipping blank lines and comments (#)."""
    urls: list[str] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls


def safe_filename(url: str, index: int) -> str:
    """Derive a safe filename from a URL path, falling back to 'file_<index>'."""
    parsed = urllib.parse.urlparse(url)
    name = Path(parsed.path).name
    # Strip query strings that may have been included in the path segment
    name = name.split("?")[0].split("&")[0]
    if not name:
        name = f"file_{index}"
    return name


def download_url(url: str, dest_dir: Path, index: int, timeout: int) -> tuple[str, bool, str]:
    """
    Download a single URL to *dest_dir*.

    Returns (url, success, message).
    """
    filename = safe_filename(url, index)
    dest = dest_dir / filename

    # Avoid overwriting: append _1, _2, … until the name is free.
    stem, suffix = dest.stem, dest.suffix
    counter = 1
    while dest.exists():
        dest = dest_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    try:
        headers = {"User-Agent": "downloadURLlist/1.0"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as out:
            out.write(resp.read())
        return url, True, str(dest)
    except urllib.error.HTTPError as exc:
        return url, False, f"HTTP {exc.code} {exc.reason}"
    except urllib.error.URLError as exc:
        return url, False, str(exc.reason)
    except OSError as exc:
        return url, False, str(exc)


def download_all(
    urls: list[str],
    dest_dir: Path,
    workers: int,
    timeout: int,
) -> None:
    """Download all URLs, printing progress and a final summary."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    total = len(urls)
    ok = 0
    failed = 0

    print(f"Downloading {total} URL(s) → {dest_dir}/  (workers={workers})\n")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(download_url, url, dest_dir, i, timeout): url
            for i, url in enumerate(urls, start=1)
        }
        for done in as_completed(futures):
            url, success, detail = done.result()
            if success:
                ok += 1
                print(f"  [OK]   {url}\n         → {detail}")
            else:
                failed += 1
                print(f"  [FAIL] {url}\n         {detail}", file=sys.stderr)

    print(f"\nDone — {ok} succeeded, {failed} failed (total {total})")
    if failed:
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="download",
        description="Download files from a URL list file (one URL per line).",
    )
    parser.add_argument(
        "url_file",
        help="Path to a text file containing one URL per line. "
             "Blank lines and lines starting with '#' are ignored.",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="downloads",
        metavar="DIR",
        help="Directory to save downloaded files (default: %(default)s).",
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=4,
        metavar="N",
        help="Number of parallel download threads (default: %(default)s).",
    )
    parser.add_argument(
        "-t", "--timeout",
        type=int,
        default=30,
        metavar="SEC",
        help="Per-request timeout in seconds (default: %(default)s).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    url_file = args.url_file
    if not os.path.isfile(url_file):
        parser.error(f"URL file not found: {url_file}")

    urls = parse_url_file(url_file)
    if not urls:
        print("No URLs found in the file — nothing to do.")
        return

    download_all(
        urls=urls,
        dest_dir=Path(args.output_dir),
        workers=max(1, args.workers),
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
