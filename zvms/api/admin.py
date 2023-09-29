from flask import Blueprint

from ..framework import (
    api_login_required,
    permission,
    api_route,
    url
)
from ..misc import Permission
from ..kernel import admin as AdminKernel

Admin = Blueprint('Admin', __name__, url_prefix='/admin')


@api_route(Admin, url.permission)
@api_login_required
@permission(Permission.ADMIN)
def alter_permission(userident: str, perm: list[int]) -> None:
    """修改他人权限"""
    AdminKernel.alter_permission(userident, perm)


@api_route(Admin, url.login)
@api_login_required
@permission(Permission.ADMIN)
def admin_login(userident: str) -> None:
    """登录他人账号"""
    AdminKernel.login(userident)
