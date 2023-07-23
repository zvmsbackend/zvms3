from flask import Blueprint, session, abort

from ..framework import (
    lengthedstr,
    ZvmsError,
    login_required,
    api_route,
    url
)
from ..util import (
    dump_object,
    execute_sql
)
from ..misc import Permission, ErrorCode

User = Blueprint('User', __name__, url_prefix='/user')


class Api:
    @staticmethod
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
        return info

    @staticmethod
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

    @staticmethod
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
            case [perm] if perm & Permission.ADMIN and not manager:
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

    @staticmethod
    def get_classes() -> list[tuple[int, str]]:
        return execute_sql('SELECT id, name FROM class').fetchall()

    @staticmethod
    def class_info(classid: int) -> tuple[str, list[tuple[int, str]]]:
        match execute_sql(
            'SELECT name FROM class '
            'WHERE id = :classid',
            classid=classid
        ).fetchone():
            case None:
                abort(404)
            case [name]: ...
        members = execute_sql(
            'SELECT userid, username '
            'FROM user '
            'WHERE classid = :classid',
            classid=classid
        ).fetchall()
        return name, members


@api_route(User, url.login)
def user_login(userident: str, password: str):
    """
    用户登录
    班级名称须调用`getUserInfo获取`  
    `userident`既可以是用户名, 又可以是用户ID. 虽然id和ident其实是同一个东西, 但后者更不明觉厉
    """
    return dump_object(Api.login(userident, password), [
        'userid', 
        'username', 
        'permission', 
        'classId'
    ])


@api_route(User, url.logout)
def user_logout():
    """登出"""
    session.clear()


@api_route(User, url['userid'])
@login_required
def get_user_info(userid: int):
    """获取用户信息"""
    return dict(zip([
        'username',
        'permission',
        'classId',
        'className'
    ], Api.user_info(userid)))


@api_route(User, url.modify_password)
@login_required
def modify_password(target: int, old: lengthedstr[32, 32], new: lengthedstr[32, 32]):
    """
    修改密码  
    普通用户修改自己密码和管理员修改他人密码用的都是同一个api
    """
    Api.modify_password(target, old, new)


@api_route(User, url('class').list, 'GET')
@login_required
def list_classes():
    return dump_object(Api.get_classes(), ['id', 'name'])


@api_route(User, url('class')['classid'], 'GET')
@login_required
def get_class_info(classid: int):
    name, members = Api.class_info(classid)
    return {
        'name': name,
        'members': dump_object(members, ['userid', 'username'])
    }
