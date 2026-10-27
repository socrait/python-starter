from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session

from starter_app.core.models import Actor, Role
from starter_app.data.query_scope import QueryScope
from starter_app.data.records import MembershipRecord


class MembershipRepository:
    def __init__(self, session: Session):
        self._session = session

    def list_memberships_for_user(self, user_id: str) -> list[MembershipRecord]:
        # Runs before an Actor exists: memberships are what an Actor is built from.
        return list(
            self._session.execute(
                select(MembershipRecord)
                .where(MembershipRecord.user_id == user_id)
                .where(MembershipRecord.deleted_at.is_(None))
                .order_by(MembershipRecord.created_at)
            )
            .scalars()
            .all()
        )

    def list_member_user_ids(self, actor: Actor, user_ids: Collection[str]) -> set[str]:
        """The subset of `user_ids` who are members of the actor's org."""
        if not user_ids:
            return set()
        predicate = QueryScope.from_actor(actor).where(MembershipRecord)
        return set(
            self._session.execute(
                select(MembershipRecord.user_id)
                .where(predicate)
                .where(MembershipRecord.user_id.in_(user_ids))
            )
            .scalars()
            .all()
        )

    def create_membership(self, *, org_id: str, user_id: str, role: Role) -> MembershipRecord:
        record = MembershipRecord(org_id=org_id, user_id=user_id, role=role)
        self._session.add(record)
        self._session.flush()
        return record
