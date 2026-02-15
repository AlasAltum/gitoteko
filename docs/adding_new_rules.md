# Adding New Rules

Rules are pluggable repository actions that follow:

- Hexagonal architecture: rule logic stays outside core scanner orchestration.
- Strategy pattern: each rule is an `Action` strategy executed by `ActionPipeline`.

## Rule contract

Implement `Action` and return an `ActionResult`:

- Input: mutable `RepoContext`
- Output: `ActionResult`
- Side effects: only those owned by the rule

Rules may read/write shared context fields:

- `repo_context.detected_extensions`
- `repo_context.metadata`

## Steps to implement a new rule

1. Create a new module in [src/git_workspace_tool/rules](../src/git_workspace_tool/rules).
2. Implement a class that extends `Action`.
3. Keep rule-specific configuration in env vars (or rule-only settings), not core CLI args.
4. Return structured `ActionResult` with useful metadata.
5. Export the rule class from [src/git_workspace_tool/rules/__init__.py](../src/git_workspace_tool/rules/__init__.py).
6. Register a new `GIT_ACTIONS` name in [src/git_workspace_tool/cli/main.py](../src/git_workspace_tool/cli/main.py) action builder.
7. Document env vars in [.env.example](../.env.example) and [README.md](../README.md).

## Minimal template

```python
from git_workspace_tool.domain.actions import Action
from git_workspace_tool.domain.entities import ActionResult, RepoContext


class MyNewRuleAction(Action):
	def execute(self, repo_context: RepoContext) -> ActionResult:
		# rule logic
		repo_context.metadata["my_rule"] = "done"
		return ActionResult(
			action_name=self.name,
			success=True,
			message="My rule executed",
			metadata={"example": True},
		)
```

## Wiring example

Add `my-new-rule` to `GIT_ACTIONS` parsing and instantiate `MyNewRuleAction`.

Then run:

```bash
export GIT_ACTIONS="detect-languages,my-new-rule"
```

## Design checklist

- Does the rule avoid changing core scanner behavior?
- Is configuration scoped to the rule?
- Does it emit deterministic, traceable `ActionResult` output?
- Is it safe in dry-run mode when applicable?
