from typing import TypedDict
from datetime import date

from flask import Blueprint, session

from ..misc import Permission, ErrorCode
from ..framework import (
    lengthedstr,
    ZvmsError,
    login_required,
    permission,
    api_route,
    url
)
from ..util import (
    username2userid,
    get_primary_key,
    dump_objects,
    execute_sql
)
from .user import UserIdAndName

Notice = Blueprint('Notice', __name__, url_prefix='/notice')


class Api:
    @staticmethod
    def send_school_notice(
        title: str,
        content: str,
        anonymous: str,
        expire: date
    ) -> None:
        sender = 0 if anonymous else session.get('userid')
        execute_sql(
            'INSERT INTO notice(title, content, sender, school, expire) '
            'VALUES(:title, :content, :sender, TRUE, :expire)',
            title=title,
            content=content,
            sender=sender,
            expire=expire
        )

    @staticmethod
    def send_notice(
        title: str,
        content: str,
        anonymous: bool,
        targets: list[str],
        expire: date
    ) -> None:
        sender = 0 if anonymous else session.get('userid')
        userids = username2userid(targets)
        execute_sql(
            'INSERT INTO notice(title, content, sender, school, expire) '
            'VALUES(:title, :content, :sender, FALSE, :expire)',
            title=title,
            content=content,
            sender=sender,
            expire=expire
        )
        noticeid = get_primary_key()[0]
        for userid in userids:
            execute_sql(
                'INSERT INTO user_notice(userid, noticeid) '
                'VALUES(:userid, :noticeid)',
                userid=userid,
                noticeid=noticeid
            )

    @staticmethod
    def my_notices() -> list[tuple[str, str, str, int, str]]:
        return execute_sql(
            'SELECT notice.title, notice.content, notice.expire, user.userid, user.username '
            'FROM notice '
            'JOIN user ON notice.sender = user.userid '
            'WHERE expire >= DATE("NOW") AND (notice.school OR notice.id IN '
            '(SELECT noticeid '
            'FROM user_notice '
            'WHERE userid = :userid '
            'UNION '
            'SELECT noticeid '
            'FROM class_notice '
            'WHERE classid = :classid)) '
            'ORDER BY notice.id DESC',
            userid=session.get('userid'),
            classid=session.get('classid')
        ).fetchall()

    @staticmethod
    def list_notices() -> list[tuple[
        int, # ID
        str, # 标题
        str, # 内容
        str, # 过期时间
        int, # 发送者ID
        str, # 发送者用户名
        list[int, str] # 目标
    ]]:
        return [
            (id, title, content, expire, senderid, sender, targets)
            for id, title, content, expire, school, senderid, sender in execute_sql(
                'SELECT notice.id, notice.title, notice.content, notice.expire, notice.school, user.userid, user.username '
                'FROM notice '
                'JOIN user ON user.userid = notice.sender '
                'WHERE {} '
                'ORDER BY notice.id DESC'.format(
                    'TRUE' if Permission.ADMIN.authorized() else 'notice.sender = :sender'
                ),
                sender=session.get('userid')
            ).fetchall()
            if (targets := list(enumerate(execute_sql(
                'SELECT user.userid, user.username '
                'FROM user_notice AS un '
                'JOIN user ON user.userid = un.userid '
                'WHERE noticeid = :noticeid',
                noticeid=id
            ))) if not school else []) or True
        ]

    @staticmethod
    def edit_notice(
        noticeid: int,
        title: str,
        content: str,
        targets: list[str]
    ) -> None:
        if execute_sql(
            'SELECT id FROM notice WHERE id = :id',
                id=noticeid).fetchone() is None:
            raise ZvmsError(ErrorCode.NOTICE_NOT_EXISTS,
                            {'noticeid': noticeid})
        if targets:
            try:
                userids = username2userid(targets)
            except ValueError as exn:
                raise ZvmsError(ErrorCode.USER_NOT_EXISTS,
                                {'userid': exn.args[0]})
            execute_sql(
                'DELETE FROM user_notice '
                'WHERE noticeid = :noticeid',
                noticeid=noticeid
            )
            for userid in userids:
                execute_sql(
                    'INSERT INTO user_notice(userid, noticeid) '
                    'VALUES(:userid, :noticeid)',
                    userid=userid,
                    noticeid=noticeid
                )
        execute_sql(
            'UPDATE notice '
            'SET title = :title, content = :content '
            'WHERE id = :id',
            id=noticeid,
            title=title,
            content=content
        )

    @staticmethod
    def delete_notice(noticeid: int) -> None:
        execute_sql('DELETE FROM user_notice WHERE noticeid = :noticeid',
                    noticeid=noticeid)
        execute_sql(
            'DELETE FROM class_notice WHERE noticeid = :noticeid', noticeid=noticeid)
        if execute_sql(
            'SELECT id FROM notice WHERE id = :noticeid',
            noticeid=noticeid
        ).fetchone() is None:
            raise ZvmsError(ErrorCode.NOTICE_NOT_EXISTS,
                            {'noticeid': noticeid})
        execute_sql('DELETE FROM notice WHERE id = :id', id=noticeid)


class NoticeInfo(TypedDict):
    id: int
    title: str
    content: str
    expire: str
    senderId: int
    senderName: str
    targets: list[UserIdAndName]


@api_route(Notice, url.list, 'GET')
@login_required
@permission(Permission.MANAGER)
def list_notices() -> list[NoticeInfo]:
    """
列出所有通知  
用于管理员的编辑通知功能
    """
    *spam, targets = Api.list_notices()
    return dump_objects(spam, NoticeInfo) | {
        'targets': dump_objects(targets, UserIdAndName)
    }


class MyNotice(TypedDict):
    title: str
    content: str
    expire: str
    senderId: int
    senderName: str



@api_route(Notice, url.me, 'GET')
@login_required
def my_notices() -> list[MyNotice]:
    """列出一个人所能看到的所有通知"""
    return dump_objects(Api.my_notices(), MyNotice)


@api_route(Notice, url.send)
@login_required
@permission(Permission.MANAGER)
def send_notice(
    title: lengthedstr[32],
    content: str,
    anonymous: bool,
    targets: list[str],
    expire: date
) -> None:
    """发送通知"""
    Api.send_notice(
        title,
        content,
        anonymous,
        targets,
        expire
    )


@api_route(Notice, url.send.school)
@login_required
@permission(Permission.MANAGER)
def send_school_notice(
    title: lengthedstr[32], 
    content: str, 
    anonymous: bool, 
    expire: date
) -> None:
    """发送全校可见的学校通知"""
    Api.send_school_notice(
        title,
        content,
        anonymous,
        expire
    )
