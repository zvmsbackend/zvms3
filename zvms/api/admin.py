from functools import reduce
from operator import or_

from flask import Blueprint, session

from ..framework import (
    ZvmsError,
    api_login_required,
    permission,
    api_route,
    url
)
from ..util import (
    execute_sql
)
from ..misc import Permission, ErrorCode

Admin = Blueprint('Admin', __name__, url_prefix='/admin')

class Api:
    @staticmethod
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
    
    @staticmethod
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


@api_route(Admin, url.permission)
@api_login_required
@permission(Permission.ADMIN)
def alter_permission(userident: str, perm: list[int]) -> None:
    """修改他人权限"""
    Api.alter_permission(userident, perm)


@api_route(Admin, url.login)
@api_login_required
@permission(Permission.ADMIN)
def admin_login(userident: str) -> None:
    """登录他人账号"""
    Api.login(userident)
