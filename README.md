# downloadURLlist

A small command-line tool to download files from a URL list.

## Features

- Reads URLs from a plain-text file (one URL per line)
- Skips blank lines and comment lines (`#`)
- Parallel downloads via a configurable thread pool
- Automatic filename collision avoidance
- Configurable per-request timeout
- Exits with a non-zero status code if any download fails

## Requirements

Python 3.10+ — no third-party packages required.

## Usage

```
python download.py <url_file> [options]
```

### Arguments

| Argument | Description |
|---|---|
| `url_file` | Path to a text file containing one URL per line |
| `-o DIR`, `--output-dir DIR` | Directory to save files (default: `downloads/`) |
| `-w N`, `--workers N` | Number of parallel download threads (default: `4`) |
| `-t SEC`, `--timeout SEC` | Per-request timeout in seconds (default: `30`) |

### URL file format

```
# This is a comment and will be skipped
https://example.com/file1.zip
https://example.com/images/photo.jpg

# Blank lines are also skipped
https://example.com/report.pdf
```

### Examples

```bash
# Download all URLs with default settings
python download.py urls.txt

# Save to a custom directory with 8 parallel threads
python download.py urls.txt -o /tmp/downloads -w 8

# Use a longer timeout for slow connections
python download.py urls.txt -t 60
```

## Running tests

```bash
python -m unittest test_download -v
```
