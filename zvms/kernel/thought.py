from typing import TypeAlias
import os.path

from flask import abort, session

from ..framework import ZvmsError
from ..util import (
    send_notice_to,
    execute_sql,
    md5
)
from ..misc import (
    ThoughtStatus,
    Permission,
    ErrorCode,
    VolType
)

SelectResult: TypeAlias = tuple[
    int,  # 总数
    list[tuple[
        int,  # 用户ID
        str,  # 用户名
        int,  # 义工ID
        str,  # 义工名
        int  # 状态
    ]]
]


def _select_thoughts(where_clause: str, args: dict, page: int) -> SelectResult:
    count = execute_sql(
        'SELECT COUNT(*) '
        'FROM user_vol AS uv '
        'JOIN volunteer AS vol ON vol.id = uv.volid '
        f'WHERE uv.status != 1 AND ({where_clause})',
        **args
    ).fetchone()[0]
    match execute_sql(
        'SELECT uv.userid, user.username, uv.volid, vol.name, uv.status '
        'FROM user_vol AS uv '
        'JOIN user ON user.userid = uv.userid '
        'JOIN volunteer AS vol ON vol.id = uv.volid '
        f'WHERE uv.status != 1 AND ({where_clause}) '
        'ORDER BY uv.volid DESC '
        'LIMIT 10 '
        'OFFSET :offset',
        **args,
        offset=page * 10
    ).fetchall():
        case None:
            abort(404)
        case data: ...
    return count, data


def list_thoughts(page: int) -> SelectResult:
    return _select_thoughts('TRUE', {}, page)


def my_thoughts(page: int) -> SelectResult:
    return _select_thoughts(
        'uv.userid = :userid',
        {
            'userid': session.get('userid')
        },
        page
    )


def unaudited_thoutghts(page: int) -> SelectResult:
    return _select_thoughts(
        'uv.status = 4 AND vol.type = :type',
        {
            'type': VolType.INSIDE if Permission.MANAGER.authorized() else VolType.OUTSIDE
        },
        page
    )


def thought_info(volid: int, userid: int) -> tuple[
    str,  # 用户名
    int,  # 班级ID
    str,  # 班级名
    str,  # 义工名
    int,  # 义工类型
    int,  # 感想状态
    str,  # 感想
    int,  # 义工时间
    int,  # 预期的义工时间
    list[str]  # 图片
]:
    match execute_sql(
        'SELECT user.username, user.classid, class.name, vol.name, vol.type, uv.status, uv.thought, uv.reward, vol.reward '
        'FROM user_vol AS uv '
        'JOIN user ON user.userid = uv.userid '
        'JOIN class ON class.id = user.classid '
        'JOIN volunteer AS vol ON vol.id = uv.volid '
        'WHERE uv.userid = :userid AND uv.volid = :volid',
        userid=userid,
        volid=volid
    ).fetchone():
        case None:
            abort(404)
        case [username, classid, *spam]: ...
    if userid != int(session.get('userid')) and not (
        (Permission.CLASS.authorized() and classid != int(session.get('classid'))) or
        (Permission.MANAGER | Permission.AUDITOR).authorized()
    ):
        raise ZvmsError(ErrorCode.NOT_AUTHORIZED)
    pictures = execute_sql(
        'SELECT filename FROM picture WHERE userid = :userid AND volid = :volid',
        userid=userid,
        volid=volid
    ).scalars().all()
    return username, classid, *spam, pictures


def prepare_edit_thought(volid: int, userid: int) -> tuple[
    str,  # 义工名称
    int,  # 感想状态
    str,  # 感想
    list[tuple[str, bool]]  # 图片
]:
    if userid != int(session.get('userid')):
        raise ZvmsError(ErrorCode.CANT_EDIT_OTHERS_THOUGHT)
    match execute_sql(
        'SELECT vol.name, uv.status, uv.thought '
        'FROM user_vol AS uv '
        'JOIN volunteer AS vol ON vol.id = uv.volid '
        'WHERE uv.userid = :userid AND uv.volid = :volid ',
        userid=userid,
        volid=volid
    ).fetchone():
        case None:
            abort(404)
        case [_, ThoughtStatus.ACCEPTED | ThoughtStatus.REJECTED | ThoughtStatus.WAITING_FOR_SIGNUP_AUDIT, _]:
            raise ZvmsError(ErrorCode.THOUGHT_NOT_EDITABLE)
        case [volname, status, thought]: ...
    pictures = execute_sql(
        'SELECT DISTINCT filename '
        'FROM picture '
        'WHERE volid = :volid',
        volid=volid
    ).scalars().all()
    pictures_used = set(execute_sql(
        'SELECT filename '
        'FROM picture '
        'WHERE volid = :volid AND userid = :userid',
        volid=volid,
        userid=userid
    ).scalars().all())
    pictures = [
        (filename, filename in pictures_used)
        for filename in pictures
    ]
    return volname, status, thought, pictures


def edit_thought(
    volid: int,
    userid: int,
    thought: str,
    pictures: list[str],
    files: list[tuple[
        str,
        bytes
    ]],
    submit: bool
) -> None:
    if userid != int(session.get('userid')):
        raise ZvmsError(ErrorCode.CANT_EDIT_OTHERS_THOUGHT)
    match execute_sql(
        'SELECT status FROM user_vol WHERE userid = :userid AND volid = :volid',
        userid=userid,
        volid=volid
    ).fetchone():
        case None:
            abort(404)
        case [ThoughtStatus.DRAFT |
              ThoughtStatus.WAITING_FOR_FIRST_AUDIT |
              ThoughtStatus.WAITING_FOR_FINAL_AUDIT] if not submit: ...
        case [ThoughtStatus.DRAFT] if submit: ...
        case _:
            raise ZvmsError(ErrorCode.THOUGHT_NOT_EDITABLE)
    execute_sql(
        'DELETE FROM picture WHERE volid = :volid AND userid = :userid',
        volid=volid,
        userid=userid
    )
    for filename in pictures:
        if execute_sql(
            'SELECT COUNT(*) FROM picture WHERE volid = :volid AND filename = :filename',
            volid=volid,
            filename=filename
        ).fetchone()[0] == 0:
            raise ZvmsError(ErrorCode.PICTURE_NOT_EXISTS,
                            {'filename': filename})
        execute_sql(
            'INSERT INTO picture(volid, userid, filename) '
            'VALUES(:volid, :userid, :filename)',
            volid=volid,
            userid=userid,
            filename=filename
        )
    for filename, data in files:
        try:
            data.decode()
        except UnicodeEncodeError: ...
        else:
            raise ZvmsError(ErrorCode.INVALID_IMAGE_FILE)
        ext = filename.split('.')[-1]
        filename = f'{md5(data)}.{ext}'
        match execute_sql(
            'SELECT * FROM picture '
            'WHERE volid = :volid AND userid = :userid AND filename = :filename',
            volid=volid,
            userid=userid,
            filename=filename
        ).fetchone():
            case None: ...
            case _:
                continue
        execute_sql(
            'INSERT INTO picture(volid, userid, filename) '
            'VALUES(:volid, :userid, :filename)',
            volid=volid,
            userid=userid,
            filename=filename
        )
        match execute_sql(
            'SELECT COUNT(*) FROM picture WHERE filename = :filename',
            filename=filename
        ).fetchone():
            case [1]: ...
            case _:
                continue
        with open(os.path.join('zvms', 'static', 'pictures', filename), 'wb') as f:
            f.write(data)
    if submit:
        execute_sql(
            'UPDATE user_vol SET thought = :thought, status = :status '
            'WHERE userid = :userid AND volid = :volid',
            thought=thought,
            status=ThoughtStatus.WAITING_FOR_FIRST_AUDIT,
            userid=userid,
            volid=volid
        )
    else:
        execute_sql(
            'UPDATE user_vol SET thought = :thought '
            'WHERE userid = :userid AND volid = :volid',
            thought=thought,
            userid=userid,
            volid=volid
        )


def first_audit(volid: int, userid: int) -> None:
    match execute_sql(
        'SELECT status FROM user_vol WHERE userid = :userid AND volid = :volid',
        userid=userid,
        volid=volid
    ).fetchone():
        case None:
            abort(404)
        case [ThoughtStatus.WAITING_FOR_FIRST_AUDIT]: ...
        case _:
            raise ZvmsError(ErrorCode.THOUGHT_NOT_AUDITABLE)
    execute_sql(
        'UPDATE user_vol SET status = 4 WHERE userid = :userid AND volid = :volid',
        userid=userid,
        volid=volid
    )
    send_notice_to(
        '感想过审',
        f'你的[感想](/thought/{volid}/{userid})已通过初审',
        userid
    )


def _test_final(volid: int, userid: int) -> None:
    match execute_sql(
        'SELECT uv.status, vol.type '
        'FROM user_vol AS uv '
        'JOIN volunteer AS vol ON vol.id = uv.volid '
        'WHERE userid = :userid AND volid = :volid',
        userid=userid,
        volid=volid
    ).fetchone():
        case None:
            abort(404)
        case [ThoughtStatus.WAITING_FOR_FINAL_AUDIT, VolType.OUTSIDE] if Permission.MANAGER.authorized(): ...
        case [ThoughtStatus.WAITING_FOR_FINAL_AUDIT, VolType.INSIDE] if Permission.AUDITOR.authorized(): ...
        case _:
            raise ZvmsError(ErrorCode.THOUGHT_NOT_AUDITABLE)


def accept_thought(volid: int, userid: int, reward: int) -> None:
    _test_final(volid, userid)
    execute_sql(
        'UPDATE user_vol '
        'SET status = 5, reward = :reward '
        'WHERE userid = :userid AND volid = :volid',
        userid=userid,
        volid=volid,
        reward=reward
    )
    send_notice_to(
        '感想过审',
        f'你的[感想](/thought/{volid}/{userid})已被接受, 获得{reward}义工时间',
        userid
    )


def _reject_or_spike(
    volid: int,
    userid: int,
    notice_content: str,
    status: ThoughtStatus
) -> None:
    _test_final(volid, userid)
    execute_sql(
        'UPDATE user_vol SET status = :status WHERE userid = :userid AND volid = :volid',
        userid=userid,
        volid=volid,
        status=status
    )
    send_notice_to(
        '义工未过审',
        f'你的[感想](/thought/{volid}/{userid}){notice_content}',
        userid
    )


def reject_thought(volid: int, userid: int) -> None:
    _reject_or_spike(
        volid,
        userid,
        '被拒绝, 不可重新提交',
        ThoughtStatus.REJECTED
    )


def spike_thought(volid: int, userid: int) -> None:
    _reject_or_spike(
        volid,
        userid,
        '被打回, 可以重新提交',
        ThoughtStatus.SPIKE
    )
