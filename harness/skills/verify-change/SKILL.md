---
name: verify-change
description: Check that a completed change is actually correct before reporting it
---

# Verify a change

Use this before you say a change is done.

1. **List the changed files.** Compare the working tree with the state you
   started from. If a file changed that the request did not require, explain it
   or revert it.
2. **Re-read the request.** For each requirement, point to the line of code or
   test that satisfies it. A requirement with no pointer is not done.
3. **Run the narrow check.** Execute the test, type check or command that covers
   the changed behaviour. Record the exact command and its result.
4. **Run the adjacent check.** Execute the test for the nearest unaffected
   behaviour to catch collateral damage.
5. **Inspect the diff.** Look for debug output, dead code, unrelated formatting,
   and accidental deletions.
6. **Report.** Name the change, the verification command, and anything you could
   not verify.

If a check fails, fix the change rather than the check. If the check itself is
wrong, report that separately and do not silently weaken it.

For a scope check, run:

```bash
python scripts/check_scope.py . src tests
```

For a readable view of a long file, run:

```bash
python scripts/read_doc.py path/to/file --lines 120
```
