from typing import TypedDict

from flask import Blueprint, session

from ..framework import (
    lengthedstr,
    api_login_required,
    api_route,
    url
)
from ..util import (
    dump_objects,
    dump_object
)
from ..misc import Permission
from ..kernel import user as UserKernel

User = Blueprint('User', __name__, url_prefix='/user')


class UserInfo(TypedDict):
    username: str
    permission: Permission
    classId: int
    className: str


class UserInfoMinus(TypedDict):
    username: str
    permission: Permission
    classId: int


@api_route(User, url.login)
def user_login(userident: str, password: str) -> UserInfoMinus:
    """
用户登录  
用户信息须通过getUserInfo获取  
`userident`既可以是用户名, 又可以是用户ID. 虽然id和ident其实是同一个东西, 但后者更不明觉厉
    """
    _, *info = UserKernel.login(userident, password)
    return dump_object(info, UserInfoMinus)


@api_route(User, url.logout)
def user_logout() -> None:
    """登出"""
    session.clear()


@api_route(User, url['userid'], 'GET')
@api_login_required
def get_user_info(userid: int) -> UserInfo:
    """获取用户信息"""
    return dump_object(UserKernel.user_info(userid), UserInfo)


@api_route(User, url.modify_password)
@api_login_required
def modify_password(
    target: int, 
    oldPassword: lengthedstr[32, 32], 
    newPassword: lengthedstr[32, 32]
) -> None:
    """
修改密码  
普通用户修改自己密码和管理员修改他人密码用的都是同一个api
    """
    UserKernel.modify_password(target, oldPassword, newPassword)


class UserSums(TypedDict):
    inside: int
    outside: int
    large: int


@api_route(User, url['userid'].time, 'GET')
@api_login_required
def get_user_time(userid: int) -> UserSums:
    """获取用户义工时间"""
    sums = UserKernel.get_time_sums(userid)
    return dump_object([sums.get(i + 1, 0) for i in range(3)], UserSums)


class ClassIdAndName(TypedDict):
    id: int
    name: str


@api_route(User, url('class').list, 'GET')
@api_login_required
def list_classes() -> list[ClassIdAndName]:
    """获取班级列表"""
    return dump_objects(UserKernel.get_classes(), ClassIdAndName)


class UserIdAndName(TypedDict):
    userid: int
    username: str


class ClassInfo(TypedDict):
    name: str
    members: list[UserIdAndName]


@api_route(User, url('class')['classid'], 'GET')
@api_login_required
def get_class_info(classid: int) -> ClassInfo:
    """获取班级信息"""
    name, members = UserKernel.class_info(classid)
    return {
        'name': name,
        'members': dump_objects(members, UserIdAndName)
    }
