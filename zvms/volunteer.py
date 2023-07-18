from urllib.parse import quote
from typing import Literal
from datetime import date

from flask import Blueprint, abort, session, redirect

from .framework import (
    ZvmsError,
    requiredlist,
    lengthedstr, 
    route, 
    permission, 
    login_required, 
    view, 
    url
)
from .util import (
    execute_sql, 
    render_template, 
    get_primary_key, 
    username2userid
)
from .misc import Permission, VolStatus, VolType, ThoughtStatus

Volunteer = Blueprint('Volunteer', __name__, url_prefix='/volunteer')

def select_volunteers(where_clause: str, args: dict, page: int, base_url: str) -> str:
    total = execute_sql(
        'SELECT COUNT(*) '
        'FROM volunteer AS vol '
        'JOIN user ON user.userid = vol.holder {}'.format(where_clause), 
        **args
    ).fetchone()[0]
    vol_info = execute_sql(
        'SELECT vol.id, vol.name, vol.status, vol.holder, user.username, vol.type '
        'FROM volunteer AS vol '
        'JOIN user ON user.userid = vol.holder '
        '{} '
        'ORDER BY vol.id DESC '
        'LIMIT 10 '
        'OFFSET :offset'.format(where_clause),
        **args,
        offset=page * 10
    ).fetchall()
    if not vol_info:
        abort(404)
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
            for id, name, status, holderid, holder, type in vol_info
        ],
        base_url=base_url,
        page=page,
        pages=range(page, min((total - 1) // 10 + 1, page + 5)),
        total=total
    )

def can_signup(volid: int):
    return execute_sql(
        'SELECT vol.time > DATE(\'NOW\') '
        'AND vol.status = 2 '
        'AND NOT EXISTS (SELECT * FROM user_vol AS uv WHERE uv.userid = :userid AND uv.volid = :volid) '
        'AND cv.max > COUNT(uv.userid) '
        'FROM class_vol AS cv '
        'LEFT JOIN user_vol AS uv ON uv.volid = cv.volid '
        'AND uv.userid IN (SELECT user.userid FROM user WHERE user.classid = cv.classid) '
        'JOIN volunteer AS vol ON vol.id = cv.volid '
        'WHERE vol.id = :volid',
        userid=session.get('userid'),
        volid=volid,
        classid=session.get('classid')
    ).fetchone()[0]

@route(Volunteer, url.search, 'GET')
@login_required
@view
def search_volunteers(name: str, page: int = 0):
    return select_volunteers(
        'WHERE name LIKE :name',
        {
            'name': '%{}%'.format(name)
        },
        page,
        '/volunteer/search?name={}&'.format(quote(name))
    )

@route(Volunteer, url.list, 'GET')
@login_required
@view
def list_volunteers(page: int = 0):
    return select_volunteers('', {}, page, '/volunteer/list')

@route(Volunteer, url.me, 'GET')
@login_required
@view
def my_volunteers(page: int = 0):
    return select_volunteers(
        'WHERE vol.holder = :userid '
        'OR vol.id IN '
        '(SELECT volid '
        'FROM user_vol '
        'WHERE userid = :userid) '
        'OR vol.id IN '
        '(SELECT volid '
        'FROM class_vol '
        'WHERE classid = :classid) '
        '{}'.format(
            'OR user.classid = :classid ' if Permission.CLASS.authorized()
            else ''
        ),
        {
            'userid': session.get('userid'),
            'classid': session.get('classid')
        },
        page,
        '/volunteer/me'
    )

@Volunteer.route('/<int:id>')
@login_required
@view
def volunteer_info(id: int):
    match execute_sql(
        'SELECT vol.name, vol.description, vol.status, vol.holder, user.username, vol.type, vol.reward '
        'FROM volunteer AS vol '
        'JOIN user ON user.userid = vol.holder '
        'WHERE vol.id = :id',
        id=id
    ).fetchone():
        case None:
            abort(404)
        case [name, description, status, holderid, holder, type, reward]:
            status = VolStatus(status)
    joiners = execute_sql(
        'SELECT uv.userid, user.username, uv.userid = :userid OR :can_view_thoughts OR (:can_view_class_thoughts AND user.classid = :classid)'
        'FROM user_vol AS uv '
        'JOIN user ON user.userid = uv.userid '
        'WHERE uv.volid = :volid AND uv.status != 1 ',
        volid=id,
        userid=session.get('userid'),
        can_view_thoughts=(Permission.MANAGER | Permission.AUDITOR).authorized(),
        can_view_class_thoughts=Permission.CLASS.authorized(),
        classid=session.get('classid')
    ).fetchall()
    signups = []
    if Permission.CLASS.authorized():
        signups = execute_sql(
            'SELECT uv.userid, user.username '
            'FROM user_vol AS uv '
            'JOIN user ON user.userid = uv.userid '
            'WHERE uv.volid = :volid AND uv.status = 1 ',
            volid=id
        )
    return render_template(
        'zvms/volunteer/volunteer.html',
        id=id,
        name=name,
        description=description,
        status=status,
        holderid=holderid,
        holder=holder,
        type=VolType(type),
        reward=reward,
        can_signup=can_signup(id),
        joiners=joiners,
        signups=signups
    )

@Volunteer.route('/create')
@login_required
@permission(Permission.MANAGER)
@view
def create_volunteer_get():
    return render_template('zvms/volunteer/create.html')

@route(Volunteer, url.create)
@login_required
@permission(Permission.MANAGER)
@view
def create_volunteer(
    name: lengthedstr[32], 
    description: str,
    time: date, 
    reward: int, 
    classes: requiredlist[int],
    classes_max: requiredlist[int]
):
    if len(classes) != len(classes_max):
        return render_template('zvms/error.html', msg='表单校验错误')
    for classid, max in zip(classes, classes_max):
        if execute_sql(
            'SELECT COUNT(userid) '
            'FROM user '
            'WHERE classid = :classid',
            classid=classid
        ).fetchone()[0] < max:
            return render_template('zvms/error.html', msg='班级{}的人数溢出'.format(classid))
    execute_sql(
        'INSERT INTO volunteer(name, description, status, holder, type, reward, time) '
        'VALUES(:name, :description, 2, :holder, 1, :reward, :time)',
        name=name,
        description=description,
        holder=session.get('userid'),
        reward=reward,
        time=time
    )
    volid = get_primary_key()[0]
    for classid, max in zip(classes, classes_max):
        execute_sql(
            'INSERT INTO class_vol(classid, volid, max) '
            'VALUES(:classid, :volid, :max)',
            classid=classid,
            volid=volid,
            max=max
        )
    return redirect('/volunteer/{}'.format(volid))

@Volunteer.route('/create/appointed')
@login_required
@view
def create_appointed_volunteer_get():
    return render_template('zvms/volunteer/create_appointed.html')

@route(Volunteer, url.create.appointed)
@login_required
@view
def create_appointed_volunteer(
    name: lengthedstr[32],
    description: str,
    type: Literal[VolType.INSIDE, VolType.OUTSIDE],
    reward: int,
    joiners: list[str]
):
    userids = username2userid(joiners)
    status = VolStatus.UNAUDITED
    if (Permission.CLASS | Permission.MANAGER).authorized(session.get('permission')):
        status = VolStatus.ACCEPTED
    execute_sql(
        'INSERT INTO volunteer(name, description, status, holder, time, type, reward) '
        'VALUES(:name, :description, :status, :holder, DATE(\'now\'), :type, :reward)',
        name=name,
        description=description,
        status=status,
        holder=session.get('userid'),
        type=type,
        reward=reward
    )
    volid = get_primary_key()[0]
    status = ThoughtStatus.WAITING_FOR_SIGNUP_AUDIT
    if (Permission.CLASS | Permission.MANAGER).authorized():
        status = ThoughtStatus.DRAFT
    for userid in userids:
        execute_sql(
            'INSERT INTO user_vol(userid, volid, status, thought, reward) '
            'VALUES(:userid, :volid, :status, \'\', 0)',
            userid=userid,
            volid=volid,
            status=status
        )
    return redirect('/volunteer/{}'.format(volid))

@route(Volunteer, url['id'].audit)
@login_required
@permission(Permission.CLASS)
@view
def audit_volunteer(id: int, status: Literal[VolStatus.ACCEPTED, VolStatus.REJECTED]):
    execute_sql(
        'UPDATE volunteer SET status = :status WHERE id = :id',
        id=id,
        status=status
    )
    return redirect('/volunteer/{}'.format(id))

@Volunteer.route('/create/special')
@login_required
@permission(Permission.MANAGER)
@view
def create_special_volunteer_get():
    return render_template('zvms/volunteer/create_special.html')

@route(Volunteer, url.create.special)
@login_required
@view
def create_special_volunteer(
    name: lengthedstr[32],
    type: VolType,
    rewards: requiredlist[str],
    joiners: requiredlist[str]
):
    if len(rewards) != len(joiners):
        return render_template('zvms/error.html', msg='表单校验错误')
    if all(map(str.isnumeric, rewards)):
        rewards = list(map(int, rewards))
    elif (reward := next(filter(str.isnumeric, rewards), None)) is not None:
        rewards = [int(reward)] * len(rewards)
    else:
        return render_template('zvms/error.html', msg='表单校验错误')
    userids = username2userid(joiners)
    execute_sql(
        'INSERT INTO volunteer(name, description, status, holder, time, type, reward) '
        'VALUES(:name, :name, 2, :holder, DATE(\'now\'), :type, :reward)',
        name=name,
        holder=session.get('userid'),
        type=type,
        reward=0
    )
    volid = get_primary_key()[0]
    for userid, reward in zip(userids, rewards):
        execute_sql(
            'INSERT INTO user_vol(userid, volid, status, thought, reward) '
            'VALUES(:userid, :volid, 5, \'\', :reward)',
            userid=userid,
            volid=volid,
            reward=reward
        )
    return redirect('/volunteer/{}'.format(volid))

@Volunteer.route('/<int:id>/signup', methods=['POST'])
@login_required
@view
def signup_volunteer(id: int):
    if not can_signup(id):
        return render_template('zvms/error.html', msg='义工{}不可报名'.format(id))
    status = ThoughtStatus.WAITING_FOR_SIGNUP_AUDIT
    if (Permission.CLASS | Permission.MANAGER).authorized():
        status = ThoughtStatus.DRAFT
    execute_sql(
        'INSERT INTO user_vol(userid, volid, status, thought, reward) '
        'VALUES(:userid, :volid, :status, \'\', 0)',
        userid=session.get('userid'),
        volid=id,
        status=status
    )
    return redirect('/volunteer/{}'.format(id))

def test_signup(userid: int, volid: int):
    match execute_sql(
        'SELECT COUNT(*) FROM user_vol WHERE userid = :userid AND volid = :volid',
        userid=userid,
        volid=volid
    ).fetchone():
        case [0]:
            raise ZvmsError('报名不存在')

@route(Volunteer, url['id'].signup.rollback)
@login_required
@view
def rollback_volunteer_signup(id: int, userid: int):
    if userid != int(session.get('userid')) and not Permission.CLASS.authorized():
        return render_template('zvms/error.html', msg='不能撤回他人的报名')
    test_signup(userid, id)
    execute_sql(
        'DELETE FROM user_vol WHERE userid = :userid AND volid = :volid',
        userid=userid,
        volid=id
    )
    return redirect('/volunteer/{}'.format(id))

@route(Volunteer, url['id'].signup.accept)
@login_required
@permission(Permission.CLASS)
@view
def accept_volunteer_signup(id: int, userid: int):
    test_signup(userid, id)
    execute_sql(
        'UPDATE user_vol SET status = 2 WHERE userid = :userid AND volid = :volid',
        volid=id,
        userid=userid
    )
    return redirect('/volunteer/{}'.format(id))

@Volunteer.route('/<int:id>/delete', methods=['POST'])
@login_required
@view
def delete_volunteer(id: int):
    match execute_sql(
        'SELECT holder FROM volunteer WHERE id = :id',
        id=id
    ).fetchone():
        case None:
            abort(404)
        case [holder]: ...
    if holder != int(session.get('userid')) and not Permission.MANAGER.authorized():
        return render_template('zvms/error.html', msg='不能删除他人的义工')
    execute_sql(
        'DELETE FROM class_vol WHERE volid = :volid',
        volid=id
    )
    execute_sql(
        'DELETE FROM user_vol WHERE volid = :volid',
        volid=id
    )
    execute_sql(
        'DELETE FROM volunteer WHERE id = :id',
        id=id
    )
    return redirect('/volunteer/list')

@Volunteer.route('/<int:id>/modify')
@login_required
@view
def modify_volunteer(id: int):
    return render_template('zvms/volunteer/modify.html')

# 啊啊啊啊真的好难写啊

# @Volunteer.route('/volunteer/<int:id>/modify')
# @login_required
# @view
# def modify_volunteer(id: int):
#     match execute_sql(
#         'SELECT holder, name, description, reward, time '
#         'FROM volunteer WHERE id = :id',
#         id=id
#     ).fetchone():
#         case None:
#             abort(404)
#         case [holder, name, description, reward, time]:
#             if holder != int(session.get('userid')) and not Permission.MANAGER.authorized():
#                 return render_template('zvms/error.html', msg='不可修改他人的义工')

# @route(Volunteer, url['id'].modify)
# @login_required
# @view
# def modify_volunteer(
#     id: int, 
#     name: lengthedstr[32],
#     description: str,
#     reward: int,
#     time: date,
#     classes: list[int],
#     classes_max: list[int]
# ):
#     match execute_sql(
#         'SELECT holder, type FROM volunteer WHERE id = :id',
#         id=id
#     ).fetchone():
#         case None:
#             abort(404)
#         case [holder, type]:
#             if holder != int(session.get('userid')) and not Permission.MANAGER.authorized():
#                 return render_template('zvms/error.html', msg='不能修改他人的义工')
#             if type != VolType.INSIDE and (classes or classes_max):
#                 return render_template('zvms/error.html', mag='该义工不可招募'.format(id))
#     if len(classes) != len(classes_max):
#         return render_template('zvms/error.html', msg='表单校验错误')
#     classes_dict = dict(zip(classes, classes_max))
#     for classid, count in execute_sql(
#         'SELECT cv.classid, COUNT(uv.userid) '
#         'FROM user_vol AS uv '
#         'JOIN class_vol AS cv ON cv.volid = uv.volid '
#         'WHERE uv.volid = :volid '
#         'GROUP BY cv.classid',
#         volid=id
#     ).fetchall():
#         if classid in classes_dict:
#             if count < classes_dict[classid]:
#                 return render_template('zvms/error.html', msg='班级{}的人数超过上限'.format(classid))
#             execute_sql(
#                 'UPDATE class_vol SET max = :max WHERE classid = :classid AND volid = :volid',
#                 max=classes_dict[classid],
#                 classid=classid,
#                 volid=id
#             )
#             del classes_dict[classid]
#     for classid, max in classes_dict.items():
#         execute_sql(
#             'INSERT INTO class_vol(:classid, :volid, :max) '
#             'VALUES(:classid, :volid, :max)',
#             classid=classid,
#             volid=id,
#             max=max
#         )
#     execute_sql(
#         'UPDATE volunteer '
#         'SET name = :name, description = :description, reward = :reward, time = :time '
#         'WHERE id = :id',
#         id=id,
#         name=name,
#         description=description,
#         reward=reward,
#         time=time
#     )
#     return redirect('/volunteer/{}'.format(id))