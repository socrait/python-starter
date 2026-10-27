import base64
import binascii
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sqlalchemy import Select, SQLColumnExpression

from starter_app.core.exceptions import InvalidCursorError

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


@dataclass(frozen=True)
class PageRequest:
    limit: int = DEFAULT_PAGE_SIZE
    cursor: str | None = None


@dataclass(frozen=True)
class PageSlice[T]:
    items: list[T]
    next_cursor: str | None


def encode_cursor(last_id: str) -> str:
    return base64.urlsafe_b64encode(last_id.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> str:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        last_id = base64.b64decode(padded, altchars=b"-_", validate=True).decode("ascii")
    except (binascii.Error, UnicodeDecodeError, ValueError) as e:
        raise InvalidCursorError(f"Undecodable cursor: {cursor[:32]}") from e
    if not last_id:
        raise InvalidCursorError("Empty cursor")
    return last_id


def apply_keyset_page[*Ts](
    stmt: Select[*Ts], id_column: SQLColumnExpression[str], page: PageRequest
) -> Select[*Ts]:
    """Order newest first by id and fetch one row past the page, to learn whether more exist.

    Ids are time-ordered (see `genpk`), so id order is creation order and needs no tie-breaker.
    """
    if page.cursor is not None:
        stmt = stmt.where(id_column < decode_cursor(page.cursor))
    return stmt.order_by(id_column.desc()).limit(page.limit + 1)


def slice_page[T](
    rows: Sequence[T], page: PageRequest, *, id_of: Callable[[T], str]
) -> PageSlice[T]:
    """Trim the extra row fetched by `apply_keyset_page` and derive the next cursor from it."""
    items = list(rows[: page.limit])
    has_more = len(rows) > page.limit
    return PageSlice(items=items, next_cursor=encode_cursor(id_of(items[-1])) if has_more else None)
