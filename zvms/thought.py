import io
import csv
import os.path

from flask import Blueprint, send_file, abort, redirect, session
from werkzeug.datastructures import FileStorage

from .util import (
    ZvmsError,
    execute_sql, 
    render_template, 
    render_markdown, 
    get_user_scores,
    md5
)
from .framework import login_required, permission, view, route, url
from .misc import Permission, ThoughtStatus, VolType

Thought = Blueprint('Thought', __name__, url_prefix='/thought')

@Thought.route('/csv')
@login_required
@permission(Permission.MANAGER)
@view
def data_csv():
    file = io.StringIO()
    writer = csv.writer(file)
    users = execute_sql(
        'SELECT user.userid, user.username, class.name '
        'FROM user '
        'JOIN class ON class.id = user.classid '
        'WHERE user.classid != 0'
    ).fetchall()
    writer.writerow(['学号', '姓名', '班级', '校内', '校外', '实践', '合计'])
    writer.writerows(
        (id, name, cls, *(d.get(i, 0) for i in range(1, 4)), sum(d.values()))
        for id, name, cls in users
        if (d := get_user_scores(id)) or True
    )
    return send_file(io.BytesIO(file.getvalue().encode()), download_name='data.csv')

def select_thoughts(where_clause: str, args: dict, page: str, base_url: str):
    total = execute_sql(
        'SELECT COUNT(*) '
        'FROM user_vol AS uv '
        'JOIN volunteer AS vol ON vol.id = uv.volid '
        'WHERE uv.status != 1 AND ({})'.format(where_clause),
        **args
    ).fetchone()[0]
    thought_info = execute_sql(
        'SELECT uv.userid, user.username, uv.volid, vol.name, uv.status '
        'FROM user_vol AS uv '
        'JOIN user ON user.userid = uv.userid '
        'JOIN volunteer AS vol ON vol.id = uv.volid '
        'WHERE uv.status != 1 AND ({}) '
        'ORDER BY uv.volid DESC '
        'LIMIT 10 '
        'OFFSET :offset'.format(where_clause),
        **args,
        offset=page * 10
    ).fetchall()
    if not thought_info:
        abort(404)
    return render_template(
        'zvms/thought/list.html',
        data=[
            (*spam, ThoughtStatus(status), ThoughtStatus(status).badge())
            for *spam, status in thought_info
        ],
        base_url=base_url,
        page=page,
        pages=range(page, min(page + 5, (total - 1) // 10 + 1)),
        total=total
    )

@route(Thought, url.list, 'GET')
@login_required
@permission(Permission.MANAGER | Permission.AUDITOR)
@view
def list_thoughts(page: int = 0):
    return select_thoughts('TRUE', {}, page, '/thought/list')

@route(Thought, url.me, 'GET')
@login_required
@view
def my_thoughts(page: int = 0):
    return select_thoughts(
        'uv.userid = :userid',
        {
            'userid': session.get('userid')
        },
        page,
        '/thought/me'
    )

@route(Thought, url.unaudited, 'GET')
@login_required
@permission(Permission.AUDITOR | Permission.MANAGER)
@view
def unaudited_thoughts(page: int = 0):
    return select_thoughts(
        'uv.status = 4 AND vol.type = :type',
        {
            'type': VolType.INSIDE if Permission.MANAGER.authorized() else VolType.OUTSIDE
        },
        page,
        '/thought/unaudited'
    )

@Thought.route('/<int:volid>/<int:userid>')
@login_required
@view
def thought_info(volid: int, userid: int):
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
        case [username, classid, classname, volname, type, status, thought, reward, expected_reward]:
            status = ThoughtStatus(status)
    if userid != int(session.get('userid')) and not (
        (Permission.CLASS.authorized() and classid != int(session.get('classid'))) or
        (Permission.MANAGER | Permission.AUDITOR).authorized()
    ):
        return render_template('zvms/error.html', msg='权限不足')
    pictures = execute_sql(
        'SELECT filename FROM picture WHERE userid = :userid AND volid = :volid',
        userid=userid,
        volid=volid
    ).scalars().all()
    return render_template(
        'zvms/thought/thought.html',
        userid=userid,
        username=username,
        classid=classid,
        classname=classname,
        volid=volid,
        volname=volname,
        type=VolType(type),
        status=status,
        thought=render_markdown(thought),
        reward=reward,
        expected_reward=expected_reward,
        pictures=list(enumerate(pictures))
    )

@Thought.route('/<int:volid>/<int:userid>/edit')
@login_required
@view
def edit_thought_get(volid: int, userid: int):
    if userid != int(session.get('userid')):
        return render_template('zvms/error.html', msg='不能编辑他人的感想')
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
            return render_template('zvms/error.html', msg='不能编辑该感想')
        case [volname, status, thought]:
            status = ThoughtStatus(status)
    pictures = execute_sql(
        'SELECT filename, userid = :userid '
        'FROM picture '
        'WHERE volid = :volid',
        userid=userid,
        volid=volid
    ).fetchall()
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
    return render_template(
        'zvms/thought/edit.html',
        userid=userid,
        volid=volid,
        volname=volname,
        status=status,
        thought=thought,
        pictures=enumerate(pictures)
    )

@route(Thought, url['volid']['userid'].edit)
@login_required
@view
def edit_thought(volid: int, userid: int, thought: str, pictures: list[str], files: list[FileStorage], submit: bool):
    from flask import request
    if userid != int(session.get('userid')):
        return render_template('zvms/error.html', msg='不能编辑他人的感想')
    match execute_sql(
        'SELECT status FROM user_vol WHERE userid = :userid AND volid = :volid',
        userid=userid,
        volid=volid
    ).fetchone():
        case None:
            abort(404)
        case [ThoughtStatus.DRAFT | ThoughtStatus.WAITING_FOR_FIRST_AUDIT | ThoughtStatus.WAITING_FOR_FINAL_AUDIT] if not submit: ...
        case [ThoughtStatus.DRAFT] if submit: ...
        case _:
            return render_template('zvms/error.html', msg='不能编辑该感想')
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
            return render_template('zvms/error.html', msg='图片{}不存在'.format(filename))
        execute_sql(
            'INSERT INTO picture(volid, userid, filename) '
            'VALUES(:volid, :userid, :filename)',
            volid=volid,
            userid=userid,
            filename=filename
        )
    for file in files:
        data = file.read()
        ext = file.filename.split('.')[-1]
        filename = '{}.{}'.format(md5(data), ext)
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
    return redirect('/thought/{}/{}'.format(volid, userid))

@route(Thought, url['volid']['userid'].audit.first)
@login_required
@permission(Permission.CLASS)
@view
def first_audit(volid: int, userid: int):
    match execute_sql(
        'SELECT status FROM user_vol WHERE userid = :userid AND volid = :volid',
        userid=userid,
        volid=volid
    ).fetchone():
        case None:
            abort(404)
        case [ThoughtStatus.WAITING_FOR_FIRST_AUDIT]: ...
        case _:
            return render_template('zvms/error.html', msg='该感想不能初审')
    execute_sql(
        'UPDATE user_vol SET status = 4 WHERE userid = :userid AND volid = :volid',
        userid=userid,
        volid=volid
    )
    return redirect('/thought/{}/{}'.format(volid, userid))

def test_final(volid: int, userid: int):
    match execute_sql(
        'SELECT uv.status, vol.type '
        'FROM user_vol AS uv '
        'JOIN volunteer AS vol ON vol.id = uv.volid'
        'WHERE userid = :userid AND volid = :volid',
        userid=userid,
        volid=volid
    ):
        case None:
            abort(404)
        case [ThoughtStatus.WAITING_FOR_FINAL_AUDIT, VolType.OUTSIDE] if Permission.MANAGER.authorized(): ...
        case [ThoughtStatus.WAITING_FOR_FINAL_AUDIT, VolType.INSIDE] if Permission.AUDITOR.authorized(): ...
        case _:
            raise ZvmsError('不能终审该感想')

@route(Thought, url['volid']['userid'].audit.final.accept)
@login_required
@permission(Permission.AUDITOR | Permission.MANAGER)
@view
def accept_thought(volid: int, userid: int, reward: int):
    test_final(volid, userid)
    execute_sql(
        'UPDATE user_vol '
        'SET status = 5, reward = :reward '
        'WHERE userid = :userid AND volid = :volid',
        userid=userid, 
        volid=volid,
        reward=reward
    )
    return redirect('/thought/{}/{}'.format(volid, userid))
        
# 为什么要叫foo这个名字呢?
# 我也不知道
def foo(status: ThoughtStatus, volid: int, userid: int) -> str:
    test_final(volid, userid)
    execute_sql(
        'UPDATE user_vol SET status = :status WHERE userid = :userid AND volid = :volid',
        userid=userid, 
        volid=volid,
        status=status
    )
    return redirect('/thought/{}/{}'.format(volid, userid))

@route(Thought, url['volid']['userid'].audit.final.reject)
@login_required
@permission(Permission.AUDITOR)
@view
def reject_thought(volid: int, userid: int):
    return foo(ThoughtStatus.REJECTED, volid, userid)

@route(Thought, url['volid']['userid'].audit.final.pitchback)
@login_required
@permission(Permission.AUDITOR)
@view
def pitchback_thought(volid: int, userid: int):
    return foo(ThoughtStatus.PITCHBACK, volid, userid)