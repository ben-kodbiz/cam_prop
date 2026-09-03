"""Daily pipeline scheduler (agentodo §46).

Runs stages in order: discovery -> download -> claim extraction -> evidence ->
review queue generation. Politely spaced; never auto-publishes high-impact claims.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

log = logging.getLogger("open-evidence.scheduler")


class Stage:
    def __init__(self, name: str, fn: Callable[[], int]) -> None:
        self.name = name
        self.fn = fn

    def run(self) -> int:
        log.info("stage %s starting", self.name)
        try:
            n = self.fn()
        except Exception:
            log.exception("stage %s failed", self.name)
            return -1
        log.info("stage %s finished: %s items", self.name, n)
        return n


class Scheduler:
    def __init__(self) -> None:
        self.stages: list[Stage] = []

    def add(self, name: str, fn: Callable[[], int]) -> Stage:
        stage = Stage(name, fn)
        self.stages.append(stage)
        return stage

    def run_all(self) -> list[tuple[str, int]]:
        """Run all stages in order; a failed stage doesn't abort the rest."""
        results = []
        for stage in self.stages:
            results.append((stage.name, stage.run()))
        return results
