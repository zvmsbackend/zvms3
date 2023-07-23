import csv
import io

from werkzeug.datastructures import FileStorage
from flask import (
    Blueprint,
    send_file,
    redirect,
)

from .util import (
    render_template,
    render_markdown,
    get_user_scores,
    execute_sql,
    pagination
)
from .framework import (
    login_required,
    permission,
    zvms_route,
    url
)
from .misc import (
    ThoughtStatus,
    Permission,
    VolType
)
from .api.thought import Api as ThoughtApi, SelectResult

Thought = Blueprint('Thought', __name__, url_prefix='/thought')


@zvms_route(Thought, url.csv, 'GET')
@login_required
@permission(Permission.MANAGER)
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


def select_thoughts(result: SelectResult, page: int, base_url: str):
    total, thoughts = result
    return render_template(
        'zvms/thought/list.html',
        data=[
            (*spam, ThoughtStatus(status), ThoughtStatus(status).badge())
            for *spam, status in thoughts
        ],
        base_url=base_url,
        page=page,
        pages=pagination(page, total),
        total=total
    )


@zvms_route(Thought, url.list, 'GET')
@login_required
@permission(Permission.MANAGER | Permission.AUDITOR)
def list_thoughts(page: int = 0):
    return select_thoughts(
        ThoughtApi.list_thoughts(page), 
        page, 
        '/thought/list'
    )


@zvms_route(Thought, url.me, 'GET')
@login_required
def my_thoughts(page: int = 0):
    return select_thoughts(
        ThoughtApi.my_thoughts(page),
        page,
        '/thought/me'
    )


@zvms_route(Thought, url.unaudited, 'GET')
@login_required
@permission(Permission.AUDITOR | Permission.MANAGER)
def unaudited_thoughts(page: int = 0):
    return select_thoughts(
        ThoughtApi.unaudited_thoutghts(page),
        page,
        '/thought/unaudited'
    )


@zvms_route(Thought, url['volid']['userid'], 'GET')
@login_required
def thought_info(volid: int, userid: int):
    (
        username,
        classid,
        class_name,
        volname,
        type,
        status,
        thought,
        reward,
        expected_reward,
        pictures
    ) = ThoughtApi.thought_info(volid, userid)
    return render_template(
        'zvms/thought/thought.html',
        userid=userid,
        username=username,
        classid=classid,
        classname=class_name,
        volid=volid,
        volname=volname,
        type=VolType(type),
        status=ThoughtStatus(status),
        thought=render_markdown(thought),
        reward=reward,
        expected_reward=expected_reward,
        pictures=list(enumerate(pictures))
    )


@zvms_route(Thought, url['volid']['userid'].edit, 'GET')
@login_required
def edit_thought_get(volid: int, userid: int):
    (
        volname, 
        status, 
        thought, 
        pictures
    ) = ThoughtApi.prepare_edit_thought(volid, userid)
    return render_template(
        'zvms/thought/edit.html',
        userid=userid,
        volid=volid,
        volname=volname,
        status=ThoughtStatus(status),
        thought=thought,
        pictures=enumerate(pictures)
    )


@zvms_route(Thought, url['volid']['userid'].edit)
@login_required
def edit_thought(
    volid: int, 
    userid: int, 
    thought: str, 
    pictures: list[str], 
    files: list[FileStorage], 
    submit: bool
):
    files = [
        (file.filename, file.read())
        for file in files
    ]
    ThoughtApi.edit_thought(
        volid,
        userid,
        thought,
        pictures,
        files,
        submit
    )
    return redirect(f'/thought/{volid}/{userid}')


@zvms_route(Thought, url['volid']['userid'].audit.first)
@login_required
@permission(Permission.CLASS)
def first_audit(volid: int, userid: int):
    ThoughtApi.first_audit(volid, userid)
    return redirect(f'/thought/{volid}/{userid}')


@zvms_route(Thought, url['volid']['userid'].audit.final.accept)
@login_required
@permission(Permission.AUDITOR | Permission.MANAGER)
def accept_thought(volid: int, userid: int, reward: int):
    ThoughtApi.accept_thought(volid, userid, reward)
    return redirect(f'/thought/{volid}/{userid}'.format(volid, userid))


@zvms_route(Thought, url['volid']['userid'].audit.final.reject)
@login_required
@permission(Permission.AUDITOR | Permission.MANAGER)
def reject_thought(volid: int, userid: int):
    ThoughtApi.reject_thought(volid, userid)
    return redirect(f'/thought/{volid}/{userid}')


@zvms_route(Thought, url['volid']['userid'].audit.final.pitchback)
@login_required
@permission(Permission.AUDITOR | Permission.MANAGER)
def pitchback_thought(volid: int, userid: int):
    ThoughtApi.pitchback_thought(volid, userid)
    return redirect(f'/thought/{volid}/{userid}')