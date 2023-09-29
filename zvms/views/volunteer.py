from typing import Literal, Callable
from operator import itemgetter
from urllib.parse import quote
from functools import partial
from datetime import date

from flask import (
    Blueprint,
    redirect,
)

from ..framework import (
    metalist,
    lengthedstr,
    ZvmsError,
    login_required,
    permission,
    zvms_route,
    url
)
from ..util import (
    render_template,
    render_markdown,
    pagination
)
from ..misc import (
    Permission,
    VolStatus,
    VolKind,
    VolType
)
from ..kernel import volunteer as VolKernel
from ..kernel.volunteer import SelectResult

Volunteer = Blueprint('Volunteer', __name__, url_prefix='/volunteer')


def select_volunteers(result: SelectResult, page: int, base_url: str) -> str:
    total, data = result
    return render_template(
        'zvms/volunteer/list.html',
        data=[
            (
                id,
                name,
                VolStatus(status),
                holderid,
                holder,
                VolType(type)
            )
            for id, name, status, holderid, holder, type in data
        ],
        base_url=base_url,
        page=page,
        pages=pagination(page, total),
        total=total
    )


@zvms_route(Volunteer, url.search, 'GET')
@login_required
def search_volunteers(name: str, page: int = 0):
    return select_volunteers(
        VolKernel.search_volunteers(name, page),
        page,
        f'/volunteer/search?name={quote(name)}&'
    )


@zvms_route(Volunteer, url.list, 'GET')
@login_required
def list_volunteers(page: int = 0):
    return select_volunteers(
        VolKernel.list_volunteers(page),
        page,
        '/volunteer/list'
    )


@zvms_route(Volunteer, url.me, 'GET')
@login_required
def my_volunteers(page: int = 0):
    return select_volunteers(
        VolKernel.my_volunteers(page),
        page,
        '/volunteer/me'
    )


@zvms_route(Volunteer, url['volid'], 'GET')
@login_required
def volunteer_info(volid: int):
    (
        name,
        description,
        status,
        holderid,
        holder,
        type,
        reward,
        time,
        can_signup,
        participants,
        signups
    ) = VolKernel.volunteer_info(volid)
    return render_template(
        'zvms/volunteer/volunteer.html',
        id=volid,
        name=name,
        description=render_markdown(description),
        status=VolStatus(status),
        holderid=holderid,
        holder=holder,
        type=VolType(type),
        reward=reward,
        time=time,
        can_signup=can_signup,
        participants=participants,
        signups=signups
    )


@zvms_route(Volunteer, url.create, 'GET')
@login_required
@permission(Permission.MANAGER)
def create_volunteer_get():
    return render_template('zvms/volunteer/create.html')


@zvms_route(Volunteer, url.create)
@login_required
@permission(Permission.MANAGER)
def create_volunteer(
    name: lengthedstr[32],
    description: str,
    time: date,
    reward: int,
    classes: metalist[int, 'required'],
    classes_max: metalist[int, 'required', 'duplcate']
):
    if len(classes) != len(classes_max):
        raise ZvmsError('表单校验错误')
    volid = VolKernel.create_volunteer(
        name,
        description,
        time,
        reward,
        list(zip(classes, classes_max))
    )
    return redirect(f'/volunteer/{volid}')


@zvms_route(Volunteer, url.create.appointed, 'GET')
@login_required
def create_appointed_volunteer_get():
    return render_template('zvms/volunteer/create_appointed.html')


@zvms_route(Volunteer, url.create.appointed)
@login_required
def create_appointed_volunteer(
    name: lengthedstr[32],
    description: str,
    type: Literal[VolType.INSIDE, VolType.OUTSIDE],
    reward: int,
    participants: list[str]
):
    volid = VolKernel.create_appointed_volunteer(
        name,
        description,
        type,
        reward,
        participants
    )
    return redirect(f'/volunteer/{volid}')


@zvms_route(Volunteer, url['volid'].audit)
@permission(Permission.CLASS)
@login_required
def audit_volunteer(
    volid: int,
    status: Literal[VolStatus.ACCEPTED, VolStatus.REJECTED]
):
    VolKernel.audit_volunteer(volid, status)
    return redirect(f'/volunteer/{volid}')


@zvms_route(Volunteer, url.create.special, 'GET')
@login_required
@permission(Permission.MANAGER)
def create_special_volunteer_get():
    return render_template('zvms/volunteer/create_special.html')


def special_volunteer_helper(
    name: str,
    type: VolType,
    rewards: list[str],
    participants: list[str],
    method: Callable[[str, str, int, list[str]], int | None],
    method_ex: Callable[[str, str, list[tuple[str, int]]], int | None]
) -> int | None:
    decimal_rewards = list(filter(str.isdecimal, rewards))
    if len(decimal_rewards) == 1:
        return method(
            name,
            type,
            int(decimal_rewards[0]),
            participants
        )
    elif len(decimal_rewards) == len(participants):
        return method_ex(
            name,
            type,
            list(zip(participants, map(int, rewards)))
        )
    else:
        raise ZvmsError('表单校验错误')


@zvms_route(Volunteer, url.create.special)
@login_required
def create_special_volunteer(
    name: lengthedstr[32],
    type: VolType,
    rewards: metalist[str, 'required', 'duplicate'],
    participants: metalist[str, 'required']
):
    return redirect('/volunteer/{}'.format(
        special_volunteer_helper(
            name,
            type,
            rewards,
            participants,
            VolKernel.create_special_volunteer,
            VolKernel.create_special_volunteer_ex
        )
    ))


@zvms_route(Volunteer, url['volid'].signup)
@login_required
def signup_volunteer(volid: int):
    VolKernel.signup_volunteer(volid)
    return redirect(f'/volunteer/{volid}')


@zvms_route(Volunteer, url['volid'].signup.rollback)
@login_required
def rollback_volunteer_signup(volid: int, userid: int):
    VolKernel.rollback_volunteer_signup(volid, userid)
    return redirect(f'/volunteer/{volid}')


@zvms_route(Volunteer, url['volid'].signup.accept)
@login_required
@permission(Permission.CLASS)
def accept_volunteer_signup(volid: int, userid: int):
    VolKernel.accept_volunteer_signup(volid, userid)
    return redirect(f'/volunteer/{volid}')


@zvms_route(Volunteer, url['volid'].delete)
@login_required
def delete_volunteer(volid: int):
    VolKernel.delete_volunteer(volid)
    return redirect('/volunteer/list')


@zvms_route(Volunteer, url['volid'].modify, 'GET')
@login_required
def modify_volunteer_get(volid: int):
    (
        kind,
        name,
        description,
        time,
        reward,
        type,
        participants,
        classes
    ) = VolKernel.prepare_modify_volunteer(volid)
    match kind:
        case VolKind.SPECIAL:
            return render_template(
                'zvms/volunteer/create_special.html',
                action=f'/volunteer/{volid}/modify/special',
                name=name,
                type=type,
                participants=participants
            )
        case VolKind.INSIDE:
            return render_template(
                'zvms/volunteer/create.html',
                action=f'/volunteer/{volid}/modify',
                name=name,
                description=description,
                time=time,
                reward=reward,
                classes=classes
            )
        case VolKind.APPOINTED:
            return render_template(
                'zvms/volunteer/create_appointed.html',
                action=f'/volunteer/{volid}/modify/appointed',
                name=name,
                description=description,
                type=type,
                reward=reward,
                participants=list(map(itemgetter(0), participants))
            )


@zvms_route(Volunteer, url['volid'].modify.special)
@login_required
@permission(Permission.MANAGER)
def modify_volunteer_special(
    volid: int,
    name: lengthedstr[32],
    type: VolType,
    rewards: metalist[str, 'required', 'duplicate'],
    participants: metalist[str, 'required']
):
    special_volunteer_helper(
        name,
        type,
        rewards,
        participants,
        partial(VolKernel.modify_special_volunteer, volid),
        partial(VolKernel.modify_special_volunteer_ex, volid)
    )
    return redirect(f'/volunteer/{volid}')


@zvms_route(Volunteer, url['volid'].modify)
@login_required
@permission(Permission.MANAGER)
def modify_volunteer(
    volid: int,
    name: lengthedstr[32],
    description: str,
    time: date,
    reward: int,
    classes: metalist[int, 'required'],
    classes_max: metalist[int, 'required', 'duplicate']
):
    if len(classes) != len(classes_max):
        raise ZvmsError('表单校验错误')
    VolKernel.modify_volunteer(
        volid,
        name,
        description,
        time,
        reward,
        list(zip(classes, classes_max))
    )
    return redirect(f'/volunteer/{volid}')


@zvms_route(Volunteer, url['volid'].modify.appointed)
@login_required
def modify_volunteer_appointed(
    volid: int,
    name: lengthedstr[32],
    description: str,
    type: Literal[VolType.INSIDE, VolType.OUTSIDE],
    reward: int,
    participants: list[str]
):
    VolKernel.modify_appointed_volunteer(
        volid,
        name,
        description,
        type,
        reward,
        participants
    )
    return redirect(f'/volunteer/{volid}')
