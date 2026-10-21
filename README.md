ASSIGNMENT C1
Build a CLI Tool from a Spec
TOOL
aXet Code	LEVEL
Intermediate	EFFORT
4 hours

Use aXet Code in the terminal to build a working log-analysis CLI from an empty folder, starting from a written spec and an agreed plan.
SCENARIO
The operations team wants a quick tool to summarise application logs after an incident, without opening a dashboard.
SPEC FOR LOGSCOPE (PYTHON OR NODE.JS)
•	logscope summary app.log – counts by level (INFO / WARN / ERROR), top 5 error messages, first and last timestamp
•	logscope timeline app.log --bucket 15m – error count per time bucket as a text bar chart
•	logscope grep app.log --level ERROR --since "2026-10-01 09:00" – filtered lines
•	--format json|md on every command; md writes a report file
•	Handles a 100 MB log without loading it fully into memory
•	Malformed lines are counted and skipped; they never crash the tool
HOW TO WORK
1.	Write SPEC.md yourself from the list above, plus a project instructions file for aXet Code.
2.	Ask aXet Code for an implementation plan first. Review and edit the plan before any code is written.
3.	Build in steps: parser → summary → timeline → grep → output formats. Let aXet Code run tests after each step, then commit.
4.	Ask it to write a generator for a 100 MB synthetic log (scripts/gen_log) and measure runtime and memory.
ACCEPTANCE CRITERIA
☐	All three commands work on the provided sample.log
☐	Unit tests for the parser and each command, all passing
☐	A 100 MB log is processed in under 60 seconds with stable memory
☐	Malformed-line count is reported
☐	Git history shows plan-then-build, not one large commit
STRETCH GOAL
Add logscope explain, which sends the top errors to an LLM (endpoint set via environment) and prints a probable root-cause summary.
SKILLS COVERED
Spec-driven prompting · planning before coding · letting the agent run commands and tests · incremental commits · performance checks
