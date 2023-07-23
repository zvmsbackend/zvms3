from typing import TypeAlias, TypedDict
from base64 import b64decode
import os.path

from flask import Blueprint, abort, session

from ..framework import (
    ZvmsError,
    login_required,
    permission,
    api_route,
    url
)
from ..misc import (
    ThoughtStatus,
    Permission,
    ErrorCode,
    VolType
)
from ..util import (
    send_notice_to,
    execute_sql,
    dump_object,
    md5
)

Thought = Blueprint('Thought', __name__, url_prefix='/thought')

SelectResult: TypeAlias = tuple[
    int, # 总数
    list[tuple[
        int, # 用户ID
        str, # 用户名
        int, # 义工ID
        str, # 义工名
        int # 状态
    ]]
]


class Api:
    @staticmethod
    def _select_thoughts(where_clause: str, args: dict, page: int) -> SelectResult:
        total = execute_sql(
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
        return total, data
    
    @staticmethod
    def list_thoughts(page: int) -> SelectResult:
        return Api._select_thoughts('TRUE', {}, page)
    
    @staticmethod
    def my_thoughts(page: int) -> SelectResult:
        return Api._select_thoughts(
            'uv.userid = :userid',
            {
                'userid': session.get('userid')
            },
            page
        )
    
    @staticmethod
    def unaudited_thoutghts(page: int) -> SelectResult:
        return Api._select_thoughts(
            'uv.status = 4 AND vol.type = :type',
            {
                'type': VolType.INSIDE if Permission.MANAGER.authorized() else VolType.OUTSIDE
            },
            page
        )
    
    @staticmethod
    def thought_info(volid: int, userid: int) -> tuple[
        str, # 用户名
        int, # 班级ID
        str, # 班级名
        str, # 义工名
        int, # 义工类型
        int, # 感想状态
        str, # 感想
        int, # 义工时间
        int, # 期望的义工时间
        list[str] # 图片
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
    
    @staticmethod
    def prepare_edit_thought(volid: int, userid: int) -> tuple[
        str, # 义工名称
        int, # 感想状态
        str, # 感想
        list[tuple[str, bool]] # 图片
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
    
    @staticmethod
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
                raise ZvmsError(ErrorCode.PICTURE_NOT_EXISTS, {'filename': filename})
            execute_sql(
                'INSERT INTO picture(volid, userid, filename) '
                'VALUES(:volid, :userid, :filename)',
                volid=volid,
                userid=userid,
                filename=filename
            )
        for filename, data in files:
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

    @staticmethod
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

    @staticmethod
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
            
    @staticmethod
    def accept_thought(volid: int, userid: int, reward: int) -> None:
        Api._test_final(volid, userid)
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

    @staticmethod
    def _reject_or_pitchback(
        volid: int, 
        userid: int,
        notice_content: str, 
        status: ThoughtStatus
    ) -> None:
        Api._test_final(volid, userid)
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

    @staticmethod
    def reject_thought(volid: int, userid: int) -> None:
        Api._reject_or_pitchback(
            volid,
            userid,
            '被拒绝, 不可重新提交',
            ThoughtStatus.REJECTED
        )

    @staticmethod
    def pitchback_thought(volid: int, userid: int) -> None:
        Api._reject_or_pitchback(
            volid,
            userid,
            '被打回, 可以重新提交',
            ThoughtStatus.PITCHBACK
        )


def select_thoughts(result: SelectResult):
    total, data = result
    return {
        'total': total,
        'data': dump_object(data, [
            'userid',
            'username'
            'volId',
            'volName',
            'status'
        ])
    }


@api_route(Thought, url.list['page'], 'GET')
@login_required
@permission(Permission.MANAGER | Permission.AUDITOR)
def list_thoughts(page: int):
    """列出感想(普通用户不能看)"""
    return select_thoughts(Api.list_thoughts(page))


@api_route(Thought, url.me['page'], 'GET')
@login_required
def my_thoughts(page: int):
    """与自己有关的感想"""
    return select_thoughts(Api.my_thoughts(page))


@api_route(Thought, url.unaudited['page'], 'GET')
@login_required
@permission(Permission.MANAGER | Permission.AUDITOR)
def unaudited_thoughts(page: int):
    """
    未审核感想  
    对于MANAGER, 列出校内义工的感想; 对于AUDITOR, 列出校外的
    """
    return select_thoughts(Api.unaudited_thoutghts(page))


@api_route(Thought, url['volid']['userid'], 'GET')
@login_required
def get_thought_info(volid: int, userid: int):
    return dict(zip([
        'username',
        'classId',
        'className',
        'volName',
        'type',
        'status',
        'thought',
        'reward',
        'expectedReward',
        'pictures'
    ], Api.thought_info(volid, userid)))


@api_route(Thought, url['volid']['userid'], 'GET')
@login_required
def prepare_edit_thought(volid: int, userid: int):
    """获取编辑感想所需的信息"""
    *spam, pictures = Api.prepare_edit_thought(volid, userid)
    return dict(zip([
        'name',
        'status',
        'thought'
    ], spam)) | {
        'pictures': dump_object(pictures, [
            'filename',
            'used'
        ])
    }


class File(TypedDict):
    filename: str
    data: str


@api_route(Thought, url['volid']['userid'].edit)
@login_required
def edit_thought(
    volid: int,
    userid: int,
    thought: str,
    pictures: list[str],
    files: list[File]
):
    _files = []
    for filename, data in files:
        try:
            files.append((filename, b64decode(data)))
        except:
            raise ZvmsError(ErrorCode.FILE_DECODE_FAILS, {'filename': filename})
    Api.edit_thought(
        volid,
        userid,
        thought,
        pictures,
        _files
    )


@api_route(Thought, url['volid']['userid'].audit.first)
@login_required
@permission(Permission.CLASS)
def first_audit(volid: int, userid: int):
    Api.first_audit(volid, userid)


@api_route(Thought, url['volid']['userid'].audit.accept)
@login_required
@permission(Permission.AUDITOR | Permission.MANAGER)
def accept_thought(volid: int, userid: int, reward: int):
    Api.accept_thought(volid, userid, reward)


@api_route(Thought, url['volid']['userid'].audit.reject)
@login_required
@permission(Permission.AUDITOR | Permission.MANAGER)
def reject_thought(volid: int, userid: int):
    Api.reject_thought(volid, userid)


@api_route(Thought, url['volid']['userid'].audit.pitchback)
@login_required
@permission(Permission.AUDITOR | Permission.MANAGER)
def pitchback_thought(volid: int, userid: int):
    Api.pitchback_thought(volid, userid)
