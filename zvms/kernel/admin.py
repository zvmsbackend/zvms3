from functools import reduce

from sqlalchemy import or_
from flask import session

from ..framework import ZvmsError
from ..misc import ErrorCode, Permission
from ..util import execute_sql


def alter_permission(userident: str, perm: list[int]) -> int:
    match execute_sql(
        'SELECT userid, permission FROM user '
        'WHERE {} = :userident'.format(
            'userid' if userident.isdecimal() else 'username'
        ),
        userident=userident
    ).fetchone():
        case None:
            raise ZvmsError(ErrorCode.USER_NOT_EXISTS, {'userid': userident})
        case [_, p] if p & Permission.ADMIN:
            raise ZvmsError(ErrorCode.NOT_AUTHORIZED)
        case [userid, _]: ...
    execute_sql(
        'UPDATE user SET permission = :perm '
        'WHERE userid = :userid',
        perm=reduce(or_, perm, 0),
        userid=userid
    )
    return userid


def login(userident: str) -> None:
    match execute_sql(
        'SELECT userid, username, permission, classid FROM user WHERE {} = :userident'.format(
            'userid' if userident.isdecimal() else 'username'
        ),
        userident=userident
    ).fetchone():
        case None:
            raise ZvmsError(ErrorCode.USER_NOT_EXISTS, {'userid': userident})
        case [_, perm, _] if perm & Permission.ADMIN:
            raise ZvmsError(ErrorCode.NOT_AUTHORIZED)
        case user_info: ...
    session.update(dict(zip(
        ('userid', 'username', 'permission', 'classid'),
        user_info
    )))
