from __future__ import annotations
"""Domain action contracts and pipeline composition primitives."""

from abc import ABC, abstractmethod
from typing import Sequence

from .entities import ActionResult, RepoContext


class Action(ABC):
    """Pluggable repository rule interface.

    Implementers should:
    - read required state from `RepoContext`,
    - update `RepoContext` for downstream rules when needed,
    - return an `ActionResult` describing success/failure.
    """

    @property
    def name(self) -> str:
        """Stable default action name used in summaries/logging."""
        return self.__class__.__name__

    @abstractmethod
    def execute(self, repo_context: RepoContext) -> ActionResult:
        """Execute action logic for a single repository.

        Args:
            repo_context: Mutable context for the current repository.

        Returns:
            ActionResult with execution outcome details.
        """
        raise NotImplementedError


class ActionPipeline:
    """Ordered sequence of `Action` instances executed per repository."""

    def __init__(self, actions: Sequence[Action]) -> None:
        """Create pipeline from an ordered list/sequence of actions."""
        self._actions = tuple(actions)

    @property
    def actions(self) -> tuple[Action, ...]:
        """Read-only ordered actions configured for this pipeline."""
        return self._actions

    def run(self, repo_context: RepoContext, *, fail_fast: bool = False) -> list[ActionResult]:
        """Run configured actions in order for one repository context.

        Args:
            repo_context: Mutable per-repository execution context.
            fail_fast: Stop executing remaining actions after first failed action.
        """
        results: list[ActionResult] = []
        for action in self._actions:
            result = action.execute(repo_context)
            if not result.action_name:
                result.action_name = action.name
            results.append(result)
            if fail_fast and not result.success:
                break
        return results
