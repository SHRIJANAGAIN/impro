# Guardrails

These rules apply to every run.

- Never delete or rewrite a file you did not read, unless the request explicitly
  names it.
- Never commit, push, tag or publish. Leave the working tree for review.
- Never write credentials, tokens or private keys into the repository. If a task
  needs one, stop and say so.
- Do not run destructive commands (`rm -rf`, `mkfs`, `shutdown`, database drops)
  without explicit approval in the request.
- Do not install global packages or change the user's machine configuration.
- Stop and report when the same command fails three times, when a required file
  does not exist, or when the change would affect code outside the requested
  scope.
- A test that passed before your change must still pass. If it does not, fix the
  change or report the regression; do not weaken the test.
- When a request would take more than one reviewable change, land the smallest
  coherent piece and report the remainder instead of sprawling.

- When you are about to claim a change is correct, use the `verify-change` skill.
