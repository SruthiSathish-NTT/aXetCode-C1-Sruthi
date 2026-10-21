# Logscope Specification

## Goal
Logscope is a command-line tool for streaming analysis of application logs after incidents.

## Technology
- Python 3.11+
- Standard library preferred
- Command name: `logscope`

## Supported log format
Each valid log line has this format:

YYYY-MM-DD HH:MM:SS LEVEL message

Example:

2026-10-01 09:00:01 INFO Application started
2026-10-01 09:05:10 ERROR Database connection refused
2026-10-01 09:06:00 WARN Retry attempt 1

Levels are `INFO`, `WARN`, and `ERROR`.

A malformed line is any line that cannot be parsed into a timestamp, supported level, and message.

## Commands

### summary
```bash
logscope summary app.log [--format json|md]
```text

Reports:
- Count by level: INFO, WARN, ERROR
- Top five ERROR messages by frequency
- First valid timestamp
- Last valid timestamp
- Malformed-line count

### timeline
```bash
logscope timeline app.log --bucket 15m [--format json|md]
```text

Reports:
- Number of ERROR lines per time bucket
- Default output is a text bar chart
- Supports minute-based bucket durations such as `15m`, `1h`
- Includes malformed-line count

### grep
```bash
logscope grep app.log --level ERROR --since "2026-10-01 09:00" [--format json|md]
```text

Reports:
- Matching original log lines
- `--level` is required
- `--since` is optional and inclusive
- Includes malformed-line count

## Output formats
- Default: human-readable terminal output
- `--format json`: emit valid JSON to stdout
- `--format md`: write a Markdown report file and print its path
- Markdown file naming should be deterministic and include the command name

## Performance and resilience
- Process logs line by line; do not load the full file into memory.
- A 100 MB log must complete in under 60 seconds in the test environment.
- Memory must remain stable relative to input size.
- Malformed lines must be counted and skipped.
- No malformed input line may crash the tool.

## Testing
- Unit tests for parser and all three commands
- Unit tests for summary, timeline, and grep
- Tests for malformed lines
- Tests for JSON and Markdown output
- Tests for bucket parsing and timestamps
- A synthetic approximately 100 MB log generator at `scripts/gen_log`

## Stretch goal
```bash
logscope explain app.log
```text

- Reads the top errors.
- Sends them to an LLM endpoint configured by environment variables.
- Prints a probable root-cause summary.
- Must fail clearly and safely if endpoint configuration is absent.
