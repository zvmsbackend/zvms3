from datetime import date

from flask import session

from ..framework import ZvmsError
from ..util import (
    username2userid,
    get_primary_key,
    execute_sql
)
from ..misc import (
    Permission,
    ErrorCode
)


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
    noticeid = get_primary_key()
    for userid in userids:
        execute_sql(
            'INSERT INTO user_notice(userid, noticeid) '
            'VALUES(:userid, :noticeid)',
            userid=userid,
            noticeid=noticeid
        )


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


def list_notices() -> list[tuple[
    int,  # ID
    str,  # 标题
    str,  # 内容
    str,  # 过期时间
    int,  # 发送者ID
    str,  # 发送者用户名
    list[tuple[int, str]]  # 目标
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
        if (targets := execute_sql(
            'SELECT user.userid, user.username '
            'FROM user_notice AS un '
            'JOIN user ON user.userid = un.userid '
            'WHERE noticeid = :noticeid',
            noticeid=id
        ).fetchall() if not school else []) or True
    ]


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
