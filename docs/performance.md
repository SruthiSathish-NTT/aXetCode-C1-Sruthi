# Logscope Performance Documentation

## Overview

Logscope processes log files one line at a time using Python generators.
Memory use is **O(1) relative to input file size** for `summary` and
`timeline`, and **O(matching lines)** for `grep` (only matched raw strings
are held in memory). There is no intermediate buffer that grows with
file size.

---

## Generating a 100 MB synthetic log

```bash
python scripts/gen_log.py --size-mb 100 --output synthetic-100mb.log
```

The generator also accepts `--malformed-rate` (default `0.02` = 2%) and
`--seed` for reproducibility.

Expected output:

```
Generating ~100.0 MB log -> synthetic-100mb.log ...
Done.
  Output file    : /path/to/logscope/synthetic-100mb.log
  Requested size : 100.0 MB
  Actual size    : 100.00 MB  (104,857,631 bytes)
  Valid lines    : ~2,200,000
  Malformed lines: ~46,000
```

---

## Measuring runtime and memory

### Linux — GNU time (detailed memory reporting)

```bash
/usr/bin/time -v python -m logscope.cli summary synthetic-100mb.log
/usr/bin/time -v python -m logscope.cli timeline synthetic-100mb.log --bucket 15m
/usr/bin/time -v python -m logscope.cli grep synthetic-100mb.log --level ERROR
```

Key fields in the `/usr/bin/time -v` output:

- `Elapsed (wall clock) time` — real runtime
- `Maximum resident set size` — peak memory in kilobytes

### macOS — BSD time

```bash
/usr/bin/time -l python -m logscope.cli summary synthetic-100mb.log
/usr/bin/time -l python -m logscope.cli timeline synthetic-100mb.log --bucket 15m
```

Key field: `maximum resident set size`.

### Windows / universal fallback (elapsed time only)

```bash
# PowerShell
Measure-Command { python -m logscope.cli summary synthetic-100mb.log }
Measure-Command { python -m logscope.cli timeline synthetic-100mb.log --bucket 15m }

# Or using Python's time module directly:
python -c "import time,subprocess,sys; t=time.perf_counter(); subprocess.run([sys.executable,'-m','logscope.cli','summary','synthetic-100mb.log']); print(f'Elapsed: {time.perf_counter()-t:.2f}s')"
```

---

## Memory stability note

Because Logscope streams input through `iter_log()` (a Python generator
backed by `for line in file`), only one log line is held in memory at any
point during parsing. Summary and timeline accumulate only small fixed-size
counters and bucket dicts. `grep` accumulates only the text of matching
lines. For a 100 MB log with 2% error rate (~44 000 ERROR lines averaging
~55 bytes each), the peak grep result set is approximately **2.4 MB** —
independent of whether the input is 10 MB or 10 GB.

---

## Actual benchmark results

### Environment

| Property | Value |
|----------|-------|
| Platform | Windows 11, Python 3.12.10 |
| Invocation | `python -m logscope.cli <command>` |
| Memory tool | not available on this platform (elapsed time only) |
| Log file | `synthetic-100mb.log` |
| Log file size | 107,115,395 bytes (102.15 MB) |
| Valid lines | 2,211,828 |
| Malformed lines | 45,936 (~2%) |
| Seed | 42 |

### Results

| Command | File size | Elapsed | Peak memory | Requirement | Result |
|---------|-----------|---------|-------------|-------------|--------|
| `logscope summary synthetic-100mb.log` | 102.15 MB | **10.87 s** | N/A (Windows) | < 60 s | **PASS** |
| `logscope timeline synthetic-100mb.log --bucket 15m` | 102.15 MB | **11.45 s** | N/A (Windows) | < 60 s | **PASS** |
| `logscope grep synthetic-100mb.log --level ERROR` | 102.15 MB | **11.50 s** | N/A (Windows) | < 60 s | **PASS** |

All three commands process a 100 MB file in approximately **11 seconds**,
well within the 60-second requirement.

Peak memory was not measurable with GNU `/usr/bin/time -v` on this Windows
environment. On Linux the expected peak is < 20 MB for summary and timeline
(counters only). For grep with `--level ERROR` on this file (~221 000
matches × ~55 bytes each) the expected peak is approximately **12 MB** for
the match list.

### Summary command tail output (sanity check)

```
  [44177]  Remote service unavailable
  [44140]  Disk write failed
  [43926]  Out of memory
Malformed lines : 45936
```

### Timeline command tail output (sanity check, 15m buckets)

```
2027-02-19 03:15:00  [   19]  ######################
2027-02-19 03:30:00  [   14]  ################
2027-02-19 03:45:00  [    7]  ########
Malformed lines : 45936
```

### Grep command tail output (sanity check)

```
Matches         : 221201
Malformed lines : 45936
```

---

## Re-running the benchmark

```bash
# Step 1: generate a fresh 100 MB log
python scripts/gen_log.py --size-mb 100 --output synthetic-100mb.log --seed 42

# Step 2: time each command (Windows PowerShell)
Measure-Command { python -m logscope.cli summary synthetic-100mb.log }
Measure-Command { python -m logscope.cli timeline synthetic-100mb.log --bucket 15m }
Measure-Command { python -m logscope.cli grep synthetic-100mb.log --level ERROR }

# Step 2 alternative: Linux / macOS
/usr/bin/time -v python -m logscope.cli summary synthetic-100mb.log
/usr/bin/time -v python -m logscope.cli timeline synthetic-100mb.log --bucket 15m
```
