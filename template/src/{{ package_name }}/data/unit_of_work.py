from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.orm import Session


class UnitOfWork:
    """Transaction boundary for one session; orchestrator entry points open it.

    The outermost `transaction()` commits on success and rolls back on any exception.
    A nested one (an orchestrator entry point called from another) joins the outer
    transaction, so cross-subsystem calls stay atomic without either side knowing who
    called whom. Repositories and services never commit.
    """

    def __init__(self, session: Session):
        self._session = session
        self._depth = 0

    @contextmanager
    def transaction(self) -> Generator[None]:
        if self._depth:
            self._depth += 1
            try:
                yield
            finally:
                self._depth -= 1
            return

        # No session.begin(): a dependency's earlier query has usually auto-begun the
        # transaction already, and a second begin() raises. Commit whatever is open.
        self._depth = 1
        try:
            yield
            self._session.commit()
        except BaseException:
            self._session.rollback()
            raise
        finally:
            self._depth = 0
