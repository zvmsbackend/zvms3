from functools import reduce
from operator import or_

from flask import (
    Blueprint,
    redirect,
    session
)

from .framework import (
    login_required,
    permission,
    route,
    view,
    url
)
from .util import render_template, execute_sql
from .misc import Permission, permission2str

Admin = Blueprint('Admin', __name__, url_prefix='/admin')


@Admin.route('/')
@login_required
@permission(Permission.ADMIN)
@view
def index():
    return render_template('zvms/admin.html', permission2str=permission2str)


@route(Admin, url.permission)
@login_required
@permission(Permission.ADMIN)
@view
def alter_permission(userident: str, perm: list[int]):
    match execute_sql(
        'SELECT userid, permission FROM user '
        'WHERE {} = :userident'.format(
            'userid' if userident.isdecimal() else 'username'
        ),
        userident=userident
    ).fetchone():
        case None:
            return render_template('zvms/error.html', msg='用户{}不存在'.format(userident))
        case [_, p] if p & Permission.ADMIN:
            return render_template('zvms/error.html', msg='用户{}权限不可修改'.format(userident))
        case [userid, _]: ...
    execute_sql(
        'UPDATE user SET permission = :perm '
        'WHERE userid = :userid',
        perm=reduce(or_, perm, 0),
        userid=userid
    )
    return redirect('/user/{}'.format(userid))


@route(Admin, url.login)
@login_required
@permission(Permission.ADMIN)
@view
def login(userident: str):
    match execute_sql(
        'SELECT userid, username, permission, classid FROM user WHERE {} = :userident'.format(
            'userid' if userident.isdecimal() else 'username'
        ),
        userident=userident
    ).fetchone():
        case None:
            return render_template('zvms/error.html', msg='用户{}不存在'.format(userident))
        case [_, perm, _] if perm & Permission.ADMIN:
            return render_template('zvms/error.html', msg='不能登录{}的账号'.format(userident))
        case user_info: ...
    session.update(dict(zip(
        ('userid', 'username', 'permission', 'classid'),
        user_info
    )))
    return redirect('/user/login')
