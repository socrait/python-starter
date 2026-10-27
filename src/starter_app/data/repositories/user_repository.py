from sqlalchemy import select
from sqlalchemy.orm import Session

from starter_app.data.records import UserRecord


class UserRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_user(self, user_id: str) -> UserRecord | None:
        # Users aren't tenant-scoped: one account can belong to several orgs.
        return self._session.execute(
            select(UserRecord).where(UserRecord.id == user_id)
        ).scalar_one_or_none()

    def create_user(self, *, email: str, display_name: str) -> UserRecord:
        record = UserRecord(email=email, display_name=display_name)
        self._session.add(record)
        self._session.flush()
        return record
