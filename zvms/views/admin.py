from flask import (
    Blueprint,
    redirect
)

from ..framework import (
    login_required,
    permission,
    zvms_route,
    url
)
from ..misc import Permission, permission2str
from ..kernel import admin as AdminKernel
from ..util import render_template

Admin = Blueprint('Admin', __name__, url_prefix='/admin')


@zvms_route(Admin, url(''), 'GET')
@login_required
@permission(Permission.ADMIN)
def index():
    return render_template('zvms/admin.html', permission2str=permission2str)


@zvms_route(Admin, url.permission)
@login_required
@permission(Permission.ADMIN)
def alter_permission(userident: str, perm: list[int]):
    userid = AdminKernel.alter_permission(userident, perm)
    return redirect(f'/user/{userid}')


@zvms_route(Admin, url.login)
@login_required
@permission(Permission.ADMIN)
def login(userident: str):
    AdminKernel.login(userident)
    return redirect('/user/login')
