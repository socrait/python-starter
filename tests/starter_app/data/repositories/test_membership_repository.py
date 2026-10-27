from sqlalchemy.orm import Session

from starter_app.core.models import Actor
from starter_app.data.repositories import MembershipRepository


def test_list_member_user_ids_keeps_only_org_members(
    session: Session, sample_member: Actor, other_member: Actor, other_org_admin: Actor
):
    members = MembershipRepository(session).list_member_user_ids(
        sample_member, {other_member.user_id, other_org_admin.user_id, "usr_unknown"}
    )

    assert members == {other_member.user_id}
