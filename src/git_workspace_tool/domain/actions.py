from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from .entities import ActionResult, RepoContext


class Action(ABC):
    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def execute(self, repo_context: RepoContext) -> ActionResult:
        raise NotImplementedError


class ActionPipeline:
    def __init__(self, actions: Sequence[Action]) -> None:
        self._actions = tuple(actions)

    @property
    def actions(self) -> tuple[Action, ...]:
        return self._actions

    def run(self, repo_context: RepoContext) -> list[ActionResult]:
        results: list[ActionResult] = []
        for action in self._actions:
            result = action.execute(repo_context)
            if not result.action_name:
                result.action_name = action.name
            results.append(result)
        return results
