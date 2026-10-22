# ASSIGNMENT C1

## Build a CLI Tool from a Spec

| Tool | Level | Effort |
|---|---|---|
| aXet Code | Intermediate | 4 hours |

Use aXet Code in the terminal to build a working log-analysis CLI from an empty folder, starting from a written specification and an agreed plan.

## Scenario

The operations team wants a quick tool to summarise application logs after an incident, without opening a dashboard.

## Specification: LogScope

Build the tool in **Python or Node.js**.

### Commands

#### Summary

```bash
logscope summary app.log
```

Outputs:

- Counts by level: `INFO`, `WARN`, and `ERROR`
- Top five error messages
- First timestamp
- Last timestamp

#### Timeline

```bash
logscope timeline app.log --bucket 15m
```

Outputs error counts per time bucket as a text bar chart.

#### Grep

```bash
logscope grep app.log --level ERROR --since "2026-10-01 09:00"
```

Outputs filtered log lines.

### General Requirements

- Support `--format json|md` on every command.
- Markdown format must write a report file.
- Process a **100 MB** log file without loading the entire file into memory.
- Count and skip malformed lines; malformed lines must never crash the tool.

## How to Work

1. Write `SPEC.md` yourself based on the requirements above.
   - Also create a project instructions file for aXet Code.

2. Ask aXet Code for an implementation plan before writing any code.
   - Review and edit the plan before implementation begins.

3. Build the tool incrementally:

   1. Parser
   2. Summary
   3. Timeline
   4. Grep
   5. Output formats

   After each step:
   - Let aXet Code run the tests.
   - Commit the completed work.

4. Ask aXet Code to create a generator for a 100 MB synthetic log:

   ```text
   scripts/gen_log
   ```

   Measure runtime and memory usage.

## Acceptance Criteria

- [ ] All three commands work on the provided `sample.log`.
- [ ] Unit tests exist for the parser and each command, and all pass.
- [ ] A 100 MB log is processed in under 60 seconds with stable memory usage.
- [ ] The malformed-line count is reported.
- [ ] Git history demonstrates plan-then-build rather than one large commit.

## Stretch Goal

Add:

```bash
logscope explain
```

This command should:

- Send the top errors to an LLM.
- Read the endpoint configuration from an environment variable.
- Print a probable root-cause summary.

## Skills Covered

- Spec-driven prompting
- Planning before coding
- Letting the agent run commands and tests
- Incremental commits
- Performance checks
