from flask import abort, session

from ..framework import ZvmsError
from ..util import execute_sql
from ..misc import (
    Permission,
    ErrorCode
)


def login(userident: str, password: str) -> list[tuple[int, str, int, int]]:
    info = execute_sql(
        'SELECT userid, username, permission, classid '
        'FROM user '
        'WHERE {} = :userident AND password = :password'.format(
            'userid' if userident.isdecimal() else 'username'
        ),
        userident=userident,
        password=password
    ).fetchone()
    if info is None:
        raise ZvmsError(ErrorCode.INCORRECT_USERNAME_OR_PASSWORD)
    session.update(dict(zip(
        ('userid', 'username', 'permission', 'classid'),
        info
    )))
    return info


def user_info(userid: int) -> tuple[str, int, int, str]:
    if (ret := execute_sql(
        'SELECT user.username, user.permission, user.classid, class.name '
        'FROM user '
        'JOIN class ON class.id = user.classid '
        'WHERE userid = :userid ',
        userid=userid,
    ).fetchone()) is None:
        abort(404)
    return ret


def modify_password(target: int, old: str, new: str) -> None:
    manager = Permission.MANAGER.authorized()
    if target != int(session.get('userid')) and not manager:
        raise ZvmsError(ErrorCode.NOT_AUTHORIZED)
    match execute_sql(
        'SELECT permission FROM user WHERE userid = :userid',
        userid=target
    ).fetchone():
        case None:
            raise ZvmsError(ErrorCode.USER_NOT_EXISTS, {'userid': target})
        case [perm] if perm & Permission.ADMIN and target != int(session.get('userid')):
            raise ZvmsError(ErrorCode.NOT_AUTHORIZED)
    if not manager and execute_sql(
        'SELECT * FROM user WHERE userid = :userid AND password = :password',
        userid=target,
        password=old
    ):
        raise ZvmsError(ErrorCode.INCORRECT_OLD_PASSWORD)
    execute_sql(
        'UPDATE user '
        'SET password = :password '
        'WHERE userid = :userid',
        userid=target,
        password=new
    )


def get_classes() -> list[tuple[int, str]]:
    return execute_sql('SELECT id, name FROM class').fetchall()


def class_info(classid: int) -> tuple[str, list[tuple[int, str]]]:
    match execute_sql(
        'SELECT name FROM class '
        'WHERE id = :classid',
        classid=classid
    ).fetchone():
        case None:
            abort(404)
        case [name]: ...
    members = list(map(tuple, execute_sql(
        'SELECT userid, username '
        'FROM user '
        'WHERE classid = :classid',
        classid=classid
    ).fetchall()))
    return name, members
