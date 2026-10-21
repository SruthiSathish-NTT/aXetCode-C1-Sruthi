Plan.md
## 1. Package and Test-File Structure

  logscope/
  ├── logscope/
  │   ├── __init__.py
  │   ├── cli.py            # argparse entry point, subcommand dispatch
  │   ├── parser.py         # line-by-line log parser
  │   ├── commands/
  │   │   ├── __init__.py
  │   │   ├── summary.py
  │   │   ├── timeline.py
  │   │   └── grep.py
  │   └── output/
  │       ├── __init__.py
  │       ├── text.py       # human-readable renderers
  │       ├── json_fmt.py   # JSON renderers
  │       └── md_fmt.py     # Markdown renderers + file writer
  ├── tests/
  │   ├── __init__.py
  │   ├── test_parser.py
  │   ├── test_summary.py
  │   ├── test_timeline.py
  │   ├── test_grep.py
  │   └── test_output.py
  ├── scripts/
  │   └── gen_log           # synthetic log generator (executable Python script)
  ├── pyproject.toml        # packaging + entry point
  └── SPEC.md

--------

## 2. Streaming Parser Design

Module:  logscope/parser.py

  parse_line(line: str) -> LogEntry | None
  iter_log(path: str) -> Iterator[LogEntry | MalformedLine]

 LogEntry  — a  dataclass  or  NamedTuple  with fields:

•  timestamp: datetime
•  level: str  — one of  INFO ,  WARN ,  ERROR
•  message: str
•  raw: str  — original untouched line (needed for grep)

 MalformedLine  — a sentinel  dataclass  with:

•  raw: str

Parsing rules:

1. Split on whitespace with  maxsplit=3 : parts must be  [date, time, level, message] .
2. Validate date+time with  datetime.strptime("%Y-%m-%d %H:%M:%S")  — catch  ValueError .
3. Validate level is in  {"INFO", "WARN", "ERROR"} .
4. Any failure → yield  MalformedLine(raw=line) .
5. File is opened with  open(path, "r", encoding="utf-8", errors="replace")  and iterated line-by-line with a  for line
in f  loop — no  read()  or  readlines() .

--------

## 3. Command Designs

### 3a. Summary ( logscope/commands/summary.py )

Algorithm (single pass over  iter_log ):

  counts = {INFO: 0, WARN: 0, ERROR: 0}
  error_freq = Counter()
  first_ts = None
  last_ts = None
  malformed = 0

  for entry in iter_log(path):
      if MalformedLine → malformed += 1; continue
      counts[entry.level] += 1
      if entry.level == ERROR:
          error_freq[entry.message] += 1
      if first_ts is None: first_ts = entry.timestamp
      last_ts = entry.timestamp

Result object —  SummaryResult  dataclass:

•  counts: dict[str, int]
•  top_errors: list[tuple[str, int]]  (up to 5, sorted descending)
•  first_ts: datetime | None
•  last_ts: datetime | None
•  malformed: int

### 3b. Timeline ( logscope/commands/timeline.py )

Bucket parsing:  parse_bucket(s: str) -> timedelta

• Regex  ^(\d+)(m|h)$ ;  m  → minutes,  h  → 60 × minutes.
• Raises  ValueError  for unrecognised format.

Bucketing:

  bucket_key(ts, bucket_td) -> datetime
      = ts - (ts - epoch) % bucket_td
      (floors the timestamp to the nearest bucket boundary)

Algorithm (single pass):

  buckets = defaultdict(int)   # datetime → error count
  malformed = 0

  for entry in iter_log(path):
      if MalformedLine → malformed += 1; continue
      if entry.level == ERROR:
          buckets[bucket_key(entry.timestamp, td)] += 1

Result object —  TimelineResult :

•  buckets: dict[datetime, int]  (sorted by key)
•  malformed: int
•  bucket_label: str  (e.g.  "15m" )

Default text output: bar chart — each row is  HH:MM  ██████  42 ; bar width scaled to terminal width or capped at 40
chars.

### 3c. Grep ( logscope/commands/grep.py )

Inputs:  path ,  level: str ,  since: datetime | None

Algorithm (single pass):

  matches = []   # list of raw strings
  malformed = 0

  for entry in iter_log(path):
      if MalformedLine → malformed += 1; continue
      if entry.level != level: continue
      if since and entry.timestamp < since: continue
      matches.append(entry.raw)

Note:  matches  holds raw strings only, keeping memory proportional to the number of matched lines, not the full file.

Result object —  GrepResult :

•  lines: list[str]
•  malformed: int

--------

## 4. JSON and Markdown Output

Module:  logscope/output/

Each renderer takes a result object and returns either a string or writes a file.

### JSON ( json_fmt.py )

•  to_json(result) -> str  using  json.dumps(..., default=str, indent=2) .
• Timestamps serialised as ISO-8601 strings via  default=str .
• Printed to stdout with  print(to_json(result)) .

### Markdown ( md_fmt.py )

•  to_md(result, command: str) -> str  — builds a Markdown string.
•  write_md(result, command: str, log_path: str) -> str  — writes file, returns path.
• Deterministic filename:  logscope_<command>_<stem>.md  where  <stem>  is  Path(log_path).stem . Example:
logscope_summary_app.md .
• File written to the current working directory.
• Path printed to stdout after writing.

### Text ( text.py )

• One renderer function per command result type.
• Uses  print()  only; no curses or rich.

### Dispatch ( cli.py )

  if args.format == "json":  print(to_json(result))
  elif args.format == "md":  path = write_md(result, cmd, args.file); print(path)
  else:                      print_text(result)

--------

## 5. Malformed-Line Handling

•  parse_line  returns  None  for any unparseable line;  iter_log  wraps this in a  MalformedLine  sentinel.
• Every command accumulates  malformed  in its own loop — no centralized exception handler.
• All output formats include a  malformed_lines  field/section.
• No  try/except  around the outer file-reading loop; only  strptime  and split validation inside  parse_line  are
guarded.
• Empty lines and lines with only whitespace are treated as malformed (they lack all four fields).

--------

## 6. Synthetic Log Generator and Benchmark

Script:  scripts/gen_log  (executable,  #!/usr/bin/env python3 )

Usage:

  python scripts/gen_log --lines 1500000 --out logs/big.log
  # or: python scripts/gen_log --mb 100 --out logs/big.log

Design:

• Uses  random  from stdlib; no external dependencies.
• Writes line by line to a file object (no buffering in memory).
• Distributes levels: 70% INFO, 20% WARN, 10% ERROR.
• Inserts ~2% malformed lines (random garbage strings).
• Timestamps start at a configurable date and increment by 1–10 seconds randomly.
• Message pool of ~20 templates per level, selected randomly.
• Estimated line length ~60 bytes → ~1.5M lines for 100 MB.

Benchmark approach:

  time python -m logscope summary logs/big.log
  time python -m logscope timeline logs/big.log --bucket 15m
  time python -m logscope grep logs/big.log --level ERROR

Target: each command < 60 s on the test machine. Memory measured with  /usr/bin/time -v  (or  psutil  if available) —
not a hard dependency.

--------

## 7. Milestones in Implementation Order

 #                  │ Name                            │ Description
────────────────────┼─────────────────────────────────┼─────────────────────────────────────────────────────────────────
 M1                 │ Project setup + parser          │  pyproject.toml , package skeleton,  parser.py , parser tests
 M2                 │ Summary command                 │  summary.py , text output, summary tests
 M3                 │ Timeline command                │  timeline.py , bar-chart text output, timeline tests
 M4                 │ Grep command                    │  grep.py , text output, grep tests
 M5                 │ JSON + Markdown output          │  json_fmt.py ,  md_fmt.py , output tests for all three commands
 M6                 │ Synthetic generator + benchmark │  scripts/gen_log , benchmark run, performance report
 M7                 │ Stretch: explain command        │  commands/explain.py , env-var config, safe failure

--------

## 8. Files per Milestone

### M1 — Project setup + parser

  logscope/__init__.py
  logscope/cli.py                  (stub: argument parsing only, no commands wired)
  logscope/parser.py
  logscope/commands/__init__.py
  logscope/output/__init__.py
  tests/__init__.py
  tests/test_parser.py
  pyproject.toml

### M2 — Summary

  logscope/commands/summary.py
  logscope/output/text.py          (summary renderer only)
  tests/test_summary.py
  logscope/cli.py                  (updated: summary subcommand wired)

### M3 — Timeline

  logscope/commands/timeline.py
  logscope/output/text.py          (updated: timeline bar chart added)
  tests/test_timeline.py
  logscope/cli.py                  (updated: timeline subcommand wired)

### M4 — Grep

  logscope/commands/grep.py
  logscope/output/text.py          (updated: grep renderer added)
  tests/test_grep.py
  logscope/cli.py                  (updated: grep subcommand wired)

### M5 — JSON + Markdown output

  logscope/output/json_fmt.py
  logscope/output/md_fmt.py
  tests/test_output.py
  logscope/cli.py                  (updated: --format dispatch wired for all commands)

### M6 — Synthetic generator + benchmark

  scripts/gen_log

(Plus benchmark results reported in the milestone summary; no source files changed.)

### M7 — Explain (stretch)

  logscope/commands/explain.py
  tests/test_explain.py
  logscope/cli.py                  (updated: explain subcommand wired)

--------

## 9. Test Commands per Milestone

All milestones assume the package is installed in editable mode first:

  pip install -e .

 Milestone       │ Test command
─────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────
 M1              │  python -m pytest tests/test_parser.py -v
 M2              │  python -m pytest tests/test_parser.py tests/test_summary.py -v
 M3              │  python -m pytest tests/test_timeline.py -v
 M4              │  python -m pytest tests/test_grep.py -v
 M5              │  python -m pytest tests/test_output.py -v
 M6              │  python scripts/gen_log --mb 100 --out /tmp/big.log && time python -m logscope summary /tmp/big.log
 M7              │  python -m pytest tests/test_explain.py -v

Full suite at any point:  python -m pytest tests/ -v

--------

## 10. Risks, Trade-offs, and Specification Ambiguities

### Risks

 Risk                                           │ Mitigation
────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────
 grep matching lines buffered in memory         │ Hold only  entry.raw  strings for matches; warn in docs if match set
                                                │ is very large
 Timeline buckets with sparse data produce gaps │ Emit only buckets that contain ≥1 ERROR; note this in text output
                                                │ header
 Terminal width unknown for bar chart           │ Default to 40-char bars; read  shutil.get_terminal_size()  with a
                                                │ fallback
  --format md  writes to cwd, may collide       │ Filename is deterministic per (command, log stem); document overwrite
                                                │ behaviour

### Design Trade-offs

 Decision                                  │ Rationale
───────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────
  dataclass  over  NamedTuple  for results │ Easier to extend; no performance concern at these volumes
 Single-pass per command                   │ Satisfies streaming requirement; no seek-back needed
  json.dumps(default=str)  for datetime    │ Simple; ISO-8601 output is unambiguous and round-trippable
 Bar chart in text output only             │ JSON and Markdown get numeric tables instead; cleaner for downstream
                                           │ consumption
  errors="replace"  on file open           │ Prevents crash on non-UTF-8 bytes; replaced bytes become malformed lines
                                           │ naturally

### Specification Ambiguities

 Ambiguity                                                │ Assumed resolution
──────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────
  --since  format for grep — time only, or full datetime? │ Accept both  YYYY-MM-DD HH:MM  and  YYYY-MM-DD HH:MM:SS ;
                                                          │ parse with  strptime  trying both
 Top-5 ERROR messages — tie-breaking order                │ Use  Counter.most_common(5) ; ties broken by insertion
                                                          │ order (Python 3.7+ dict stability)
 Timeline default bucket size                             │ SPEC says  --bucket  is required for  timeline ; no default
                                                          │ assumed
 Markdown file written to cwd or same dir as log?         │ Written to cwd; this is predictable for the user and avoids
                                                          │ permission issues with read-only log dirs
  explain  LLM endpoint env vars — names not specified    │ Will define  LOGSCOPE_LLM_URL ,  LOGSCOPE_LLM_KEY ,
                                                          │ LOGSCOPE_LLM_MODEL ; document clearly
 Bar chart scale — per-bucket or global max?              │ Bars scaled relative to the bucket with the highest count
                                                          │ (global max within the result set)

--------