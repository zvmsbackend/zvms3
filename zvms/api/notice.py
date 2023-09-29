from typing import TypedDict
from datetime import date

from flask import Blueprint

from ..misc import Permission
from ..framework import (
    lengthedstr,
    api_login_required,
    permission,
    api_route,
    url
)
from ..util import (
    dump_objects,
    dump_object
)
from .user import UserIdAndName
from ..kernel import notice as NoticeKernel

Notice = Blueprint('Notice', __name__, url_prefix='/notice')


class NoticeInfo(TypedDict):
    id: int
    title: str
    content: str
    expire: str
    senderId: int
    senderName: str
    targets: list[UserIdAndName]


@api_route(Notice, url.list, 'GET')
@api_login_required
@permission(Permission.MANAGER)
def list_notices() -> list[NoticeInfo]:
    """
列出所有通知  
用于管理员的编辑通知功能
    """
    return [
        dump_object(spam, NoticeInfo) | {
            'targets': dump_objects(targets, UserIdAndName)}
        for *spam, targets in NoticeKernel.list_notices()
    ]


class MyNotice(TypedDict):
    title: str
    content: str
    expire: str
    senderId: int
    senderName: str


@api_route(Notice, url.me, 'GET')
@api_login_required
def my_notices() -> list[MyNotice]:
    """列出一个人所能看到的所有通知"""
    return dump_objects(NoticeKernel.my_notices(), MyNotice)


@api_route(Notice, url.send)
@api_login_required
@permission(Permission.MANAGER)
def send_notice(
    title: lengthedstr[32],
    content: str,
    anonymous: bool,
    targets: list[str],
    expire: date
) -> None:
    """发送通知"""
    NoticeKernel.send_notice(
        title,
        content,
        anonymous,
        targets,
        expire
    )


@api_route(Notice, url.send.school)
@api_login_required
@permission(Permission.MANAGER)
def send_school_notice(
    title: lengthedstr[32],
    content: str,
    anonymous: bool,
    expire: date
) -> None:
    """发送全校可见的学校通知"""
    NoticeKernel.send_school_notice(
        title,
        content,
        anonymous,
        expire
    )
