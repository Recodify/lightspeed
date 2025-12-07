## as-is

the harness expected projects to live at the repo root.

## to-be

allow a different project root to be specified using an envvar (scope:global/per tty) or passed via the cli (scope:per run) or perhaps even a ~/config/lightspeed.yaml or ~/.lightspeedrc

## Justification
this project is intended to be a tool, not a repo. By allowing detachment, we can provide a way for a user to continue using their own
dev workflow/define these projects inside their own repos.