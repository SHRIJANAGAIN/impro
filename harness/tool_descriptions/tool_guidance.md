# Tool guidance

- **Read before write.** Read the exact region you intend to change, including
  the lines directly above and below it.
- **Search before create.** A helper, type or constant with the name you need may
  already exist. Search the repository first.
- **One change at a time.** Make a coherent edit, then run the narrow check, then
  continue. A large batch of untested edits makes a failure hard to localise.
- **Quote paths.** Paths with spaces or shell metacharacters must be quoted.
- **Use the project's commands.** Check the README, Makefile, package manifest or
  CI configuration for the canonical test and lint commands instead of inventing
  one.
- **Keep output small.** Pipe long command output through a filter or read the
  relevant tail; a wall of text hides the error.
- **Scripts are helpers, not substitutes for reading.** `scripts/read_doc.py`
  prints a file with line numbers and `scripts/check_scope.py` lists files
  outside the declared scope. Use them when they save a step, and inspect their
  output critically.
