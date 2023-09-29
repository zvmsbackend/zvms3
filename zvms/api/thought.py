from typing import TypedDict
from base64 import b64decode

from flask import Blueprint

from ..framework import (
    ZvmsError,
    api_login_required,
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
    dump_objects,
    dump_object,
)
from ..kernel.thought import SelectResult
from ..kernel import thought as ThoughtKernel

Thought = Blueprint('Thought', __name__, url_prefix='/thought')


class ThoughtProfile(TypedDict):
    userid: int
    username: str
    volId: int
    volName: str
    status: ThoughtStatus


class SelectThoughts(TypedDict):
    count: int
    data: list[ThoughtProfile]


def select_thoughts(result: SelectResult) -> SelectThoughts:
    count, data = result
    return {
        'count': count,
        'data': dump_objects(data, ThoughtProfile)
    }


@api_route(Thought, url.list['page'], 'GET')
@api_login_required
@permission(Permission.MANAGER | Permission.AUDITOR)
def list_thoughts(page: int) -> SelectThoughts:
    """列出感想(普通用户不能看)"""
    return select_thoughts(ThoughtKernel.list_thoughts(page))


@api_route(Thought, url.me['page'], 'GET')
@api_login_required
def my_thoughts(page: int) -> SelectThoughts:
    """与自己有关的感想"""
    return select_thoughts(ThoughtKernel.my_thoughts(page))


@api_route(Thought, url.unaudited['page'], 'GET')
@api_login_required
@permission(Permission.MANAGER | Permission.AUDITOR)
def unaudited_thoughts(page: int) -> SelectThoughts:
    """
未审核感想  
对于MANAGER, 列出校内义工的感想; 对于AUDITOR, 列出校外的
    """
    return select_thoughts(ThoughtKernel.unaudited_thoutghts(page))


class ThoughtInfo(TypedDict):
    username: str
    classId: int
    className: str
    volName: str
    type: VolType
    status: ThoughtStatus
    thought: str
    reward: int
    expectedReward: int
    pictures: list[str]


@api_route(Thought, url['volid']['userid'], 'GET')
@api_login_required
def get_thought_info(volid: int, userid: int) -> ThoughtInfo:
    """获取感想信息"""
    *spam, pictures = ThoughtKernel.thought_info(volid, userid)
    return dump_object(spam, ThoughtInfo) | {
        'pictures': pictures
    }


class Picture(TypedDict):
    filename: str
    used: bool


class ThoughtEditingPreparation(TypedDict):
    name: str
    status: ThoughtStatus
    thought: str
    pictures: list[Picture]


@api_route(Thought, url['volid']['userid'].edit.prepare, 'GET')
@api_login_required
def prepare_edit_thought(volid: int, userid: int) -> ThoughtEditingPreparation:
    """获取编辑感想所需的信息"""
    *spam, pictures = ThoughtKernel.prepare_edit_thought(volid, userid)
    return dump_object(spam, ThoughtEditingPreparation) | {
        'pictures': dump_objects(pictures, Picture)
    }


class File(TypedDict):
    filename: str
    data: str


@api_route(Thought, url['volid']['userid'].edit)
@api_login_required
def edit_thought(
    volid: int,
    userid: int,
    thought: str,
    submit: bool,
    pictures: list[str],
    files: list[File]
) -> None:
    """编辑感想"""
    _files = []
    for filename, data in files:
        try:
            files.append((filename, b64decode(data)))
        except:
            raise ZvmsError(ErrorCode.FILE_DECODE_FAILS,
                            {'filename': filename})
    ThoughtKernel.edit_thought(
        volid,
        userid,
        thought,
        pictures,
        _files,
        submit
    )


@api_route(Thought, url['volid']['userid'].audit.first)
@api_login_required
@permission(Permission.CLASS)
def first_audit(volid: int, userid: int) -> None:
    """初审感想(团支书)"""
    ThoughtKernel.first_audit(volid, userid)


@api_route(Thought, url['volid']['userid'].audit.accept)
@api_login_required
@permission(Permission.AUDITOR | Permission.MANAGER)
def accept_thought(volid: int, userid: int, reward: int) -> None:
    """接受感想"""
    ThoughtKernel.accept_thought(volid, userid, reward)


@api_route(Thought, url['volid']['userid'].audit.reject)
@api_login_required
@permission(Permission.AUDITOR | Permission.MANAGER)
def reject_thought(volid: int, userid: int) -> None:
    """拒绝感想(不可重新提交)"""
    ThoughtKernel.reject_thought(volid, userid)


@api_route(Thought, url['volid']['userid'].audit.spike)
@api_login_required
@permission(Permission.AUDITOR | Permission.MANAGER)
def spike_thought(volid: int, userid: int) -> None:
    """打回感想"""
    ThoughtKernel.spike_thought(volid, userid)
