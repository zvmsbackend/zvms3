from typing import Literal, TypedDict
from operator import itemgetter
from datetime import date

from flask import Blueprint

from ..framework import (
    metalist,
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
from ..misc import (
    Permission,
    VolStatus,
    VolKind,
    VolType
)
from .user import UserIdAndName
from ..kernel import volunteer as VolKernel
from ..kernel.volunteer import SelectResult

Volunteer = Blueprint('Volunteer', __name__, url_prefix='/volunteer')


class VolunteerProfile(TypedDict):
    id: int
    name: str
    status: VolStatus
    holderId: int
    holderName: str
    type: VolType


class SelectVolunteers(TypedDict):
    count: int
    data: list[VolunteerProfile]


def select_volunteers(result: SelectResult) -> SelectVolunteers:
    count, data = result
    return {
        'total': count,
        'data': dump_objects(data, VolunteerProfile)
    }


@api_route(Volunteer, url.search['name', 'string']['page'], 'GET')
@api_login_required
def search_volunteers(name: str, page: int) -> SelectVolunteers:
    """搜索义工"""
    return select_volunteers(VolKernel.search_volunteers(name, page))


@api_route(Volunteer, url.list['page'], 'GET')
@api_login_required
def list_volunteers(page: int) -> SelectVolunteers:
    """列出所有义工"""
    return select_volunteers(VolKernel.list_volunteers(page))


@api_route(Volunteer, url.me['page'], 'GET')
@api_login_required
def my_volunteers(page: int) -> SelectVolunteers:
    """列出和自己有关的义工"""
    return select_volunteers(VolKernel.my_volunteers(page))


class Participant(TypedDict):
    userid: int
    username: str
    thoughtVisible: bool


class VolunteerInfo(TypedDict):
    name: str
    description: str
    status: VolStatus
    holderId: int
    holderName: str
    type: VolType
    reward: int
    canSignup: bool
    participants: list[Participant]
    signups: list[UserIdAndName]


@api_route(Volunteer, url['volid'], 'GET')
@api_login_required
def get_volunteer_info(volid: int) -> VolunteerInfo:
    """获取义工信息"""
    *spam, participants, signups = VolKernel.volunteer_info(volid)
    return dump_object(spam, VolunteerInfo) | {
        'participants': dump_objects(participants, Participant),
        'signups': dump_objects(signups, UserIdAndName)
    }


class Class(TypedDict):
    id: int
    max: int


def flatten_json_classes(classes: list[Class]) -> list[tuple]:
    return list(map(itemgetter('id', 'max'), classes))


@api_route(Volunteer, url.create)
@api_login_required
@permission(Permission.MANAGER)
def create_volunteer(
    name: lengthedstr[32],
    description: str,
    time: date,
    reward: int,
    classes: metalist[Class, 'required']
) -> int:
    """创建校内义工"""
    return VolKernel.create_volunteer(
        name,
        description,
        time,
        reward,
        flatten_json_classes(classes)
    )


@api_route(Volunteer, url.create.appointed)
@api_login_required
def create_appointed_volunteer(
    name: str,
    description: str,
    type: Literal[VolType.INSIDE, VolType.OUTSIDE],
    reward: int,
    participants: metalist[str, 'required']
) -> int:
    """创建指定义工"""
    return VolKernel.create_appointed_volunteer(
        name,
        description,
        type,
        reward,
        participants
    )


@api_route(Volunteer, url['volid'].audit)
@api_login_required
@permission(Permission.CLASS)
def audit_volunteer(
    volid: int,
    status: Literal[VolStatus.ACCEPTED, VolStatus.REJECTED]
) -> None:
    """审核义工(团支书)"""
    VolKernel.audit_volunteer(volid, status)


class ParticipantWithReward(TypedDict):
    userident: str
    reward: int


@api_route(Volunteer, url.create.special)
@api_login_required
@permission(Permission.MANAGER)
def create_special_volunteer(
    name: str,
    type: VolType,
    reward: int,
    participants: list[str]
) -> int:
    """创建特殊义工"""
    return VolKernel.create_special_volunteer(
        name,
        type,
        reward,
        participants
    )


@api_route(Volunteer, url.create.special.ex)
@api_login_required
@permission(Permission.MANAGER)
def create_special_volunteer_ex(
    name: str,
    type: VolType,
    participants: list[ParticipantWithReward]
) -> int:
    """创建特殊义工, 但是每个人的时间不一样"""
    return VolKernel.create_special_volunteer_ex(
        name,
        type,
        list(map(itemgetter('userident', 'reward'), participants))
    )


@api_route(Volunteer, url['volid'].signup)
@api_login_required
def signup_volunteer(volid: int) -> None:
    """报名义工"""
    VolKernel.signup_volunteer(volid)


@api_route(Volunteer, url['volid'].signup.rollback)
@api_login_required
def rollback_volunteer_signup(volid: int, userid: int) -> None:
    """撤回义工报名"""
    VolKernel.rollback_volunteer_signup(volid, userid)


@api_route(Volunteer, url['volid'].signup.accept)
@api_login_required
@permission(Permission.CLASS)
def accept_volunteer_signup(volid: int, userid: int) -> None:
    """接受报名(团支书)"""
    VolKernel.accept_volunteer_signup(volid, userid)


@api_route(Volunteer, url['volid'].delete)
@api_login_required
def delete_volunteer(volid: int) -> None:
    """删除义工"""
    VolKernel.delete_volunteer(volid)


class VolunteerModificationPreparation(TypedDict):
    kind: VolKind
    name: str
    description: str
    time: str
    reward: int
    type: VolType


@api_route(Volunteer, url['volid'].modify.prepare, 'GET')
@api_login_required
def prepare_modify_volunteer(volid: int) -> VolunteerModificationPreparation:
    """
获取修改义工所必须的信息

1. kind为1(INSIDE)时, 忽略participants字段
2. kind为2(APPOINTED)时, 忽略participants.reward字段和classes字段
3. kind为3(SPECIAL)时, 忽略classes字段
    """
    *spam, participants, classes = VolKernel.prepare_modify_volunteer(volid)
    return dump_object(spam, VolunteerModificationPreparation) | {
        'participants': dump_objects(participants, UserIdAndName),
        'classes': dump_objects(classes, Class)
    }


@api_route(Volunteer, url['volid'].modify.special.ex)
@api_login_required
@permission(Permission.MANAGER)
def modify_special_volunteer_ex(
    volid: int,
    name: lengthedstr[32],
    type: VolType,
    participants: list[ParticipantWithReward]
) -> None:
    """修改特殊义工"""
    VolKernel.modify_special_volunteer_ex(
        volid,
        name,
        type,
        list(map(itemgetter('userident', 'reward'), participants))
    )


@api_route(Volunteer, url['volid'].modify.special)
@api_login_required
@permission(Permission.MANAGER)
def modify_special_volunteer(
    volid: int,
    name: lengthedstr[32],
    type: VolType,
    reward: int,
    participants: list[str]
) -> None:
    """修改特殊义工"""
    VolKernel.modify_special_volunteer(
        volid,
        name,
        type,
        reward,
        participants
    )


@api_route(Volunteer, url['volid'].modify)
@api_login_required
@permission(Permission.MANAGER)
def modify_volunteer(
    volid: int,
    name: lengthedstr[32],
    description: str,
    time: date,
    reward: int,
    classes: list[Class]
) -> None:
    """修改校内义工"""
    VolKernel.modify_volunteer(
        volid,
        name,
        description,
        time,
        reward,
        flatten_json_classes(classes)
    )


@api_route(Volunteer, url['volid'].modify.appointed)
@api_login_required
def modify_appointed_volunteer(
    volid: int,
    name: lengthedstr[32],
    description: str,
    type: Literal[VolType.INSIDE, VolType.OUTSIDE],
    reward: int,
    participants: list[str]
) -> None:
    """修改指定义工"""
    VolKernel.modify_appointed_volunteer(
        volid,
        name,
        description,
        type,
        reward,
        participants
    )
