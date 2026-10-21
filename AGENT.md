# Instructions for aXet Code

## Working method
1. Read SPEC.md before proposing or writing changes.
2. Do not write code until an implementation plan has been reviewed and approved.
3. Work in small milestones only:
   - project setup and parser
   - summary
   - timeline
   - grep
   - JSON and Markdown formatting
   - synthetic-log generator and performance measurement
4. After each milestone:
   - run relevant tests;
   - report the exact test command and result;
   - provide a list of every created, changed, and deleted file;
   - provide complete contents of created or changed text files;
   - do not make unrelated changes.
5. Wait for confirmation before starting the next milestone.

## Manual-transfer requirements
- The user will manually upload your output to a VS Code web workspace.
- Treat each milestone as a complete handoff.
- Clearly label every file with its relative path.
- Do not assume Git is available.
- Do not refer to unshared files or local state from prior milestones.
- Preserve compatibility with files already delivered unless an explicit replacement is requested.

## Engineering rules
- Stream logs one line at a time.
- Never use read(), readlines(), or any approach that loads the entire input log at once.
- Keep parser, command logic, and output formatting separated.
- Count and skip malformed lines; never crash because of one.
- Preserve raw matching lines for grep.
- Use standard-library dependencies where possible.
- Add deterministic automated tests.
