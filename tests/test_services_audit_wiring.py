"""
Unit tests for the audit/transaction wiring of the service domain.

These use a tiny fake session so the ordering guarantee can be proven without a
database: the before_commit hook must receive the written row's id and must run
*before* the commit, so an admin audit row is part of the same transaction.
"""

import asyncio
import unittest

from app.modules.services.services.service_service import ServiceService


class _FakeSession:
    def __init__(self):
        self.events: list[str] = []

    async def commit(self) -> None:
        self.events.append("commit")


class FinishOrderingTests(unittest.TestCase):
    def _service(self):
        # __init__ only builds repositories around the session; nothing queries.
        session = _FakeSession()
        return ServiceService(session), session

    def test_hook_receives_id_and_runs_before_commit(self):
        service, session = self._service()
        seen: list[int] = []

        async def hook(target_id: int) -> None:
            seen.append(target_id)
            session.events.append("audit")

        asyncio.run(service._finish(hook, 42))

        self.assertEqual(seen, [42])
        self.assertEqual(session.events, ["audit", "commit"])

    def test_no_hook_still_commits(self):
        service, session = self._service()
        asyncio.run(service._finish(None, 7))
        self.assertEqual(session.events, ["commit"])


if __name__ == "__main__":
    unittest.main()
