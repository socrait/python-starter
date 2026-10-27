from enum import StrEnum
from uuid import uuid7


class IdPrefix(StrEnum):
    ORG = "org"
    USER = "usr"
    MEMBERSHIP = "mem"
    PROJECT = "prj"
    TASK = "tsk"


def genpk(prefix: IdPrefix) -> str:
    """A prefixed, time-ordered id: ids of one prefix sort in creation order."""
    return f"{prefix.value}_{uuid7().hex}"
