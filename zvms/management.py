from flask import Blueprint, render_template, redirect, session

from .util import execute_sql, username2userid, get_primary_key, render_template
from .framework import permission, login_required, route, view, url
from .misc import Permission

Management = Blueprint('Management', __name__, url_prefix='/management')

@Management.route('/')
@login_required
@permission(Permission.MANAGER)
@view
def index():
    return render_template(
        'zvms/management.html',
        issues=execute_sql(
            'SELECT issue.author, user.username, issue.content, issue.time '
            'FROM issue '
            'JOIN user ON issue.author = user.userid '
            'ORDER BY issue.id DESC'
        ).fetchall()
    )

@route(Management, url.send_notice)
@login_required
@permission(Permission.MANAGER)
@view
def send_notice(title: str, content: str, school: bool, anonymous: bool, targets: list[str]):
    sender = 0 if anonymous else session.get('userid')
    if school:
        execute_sql(
            'INSERT INTO notice(title, content, sender, school) '
            'VALUES(:title, :content, :sender, TRUE)',
            title=title,
            content=content,
            sender=sender
        )
    else:
        if not targets:
            return render_template('zvms/error.html', msg='应至少提供一个目标')
        userids = username2userid(targets)
        execute_sql(
            'INSERT INTO notice(title, content, sender, school) '
            'VALUES(:title, :content, :sender, FALSE)',
            title=title,
            content=content,
            sender=sender,
        )
        noticeid = get_primary_key()[0]
        for userid in userids:
            execute_sql(
                'INSERT INTO user_notice(userid, noticeid) '
                'VALUES(:userid, :noticeid)',
                userid=userid,
                noticeid=noticeid
            )
    return redirect('/management')

@Management.route('/edit-notices')
@login_required
@permission(Permission.MANAGER)
@view
def edit_notices_get():
    return render_template(
        'zvms/edit_notices.html',
        notices=[
            (id, title, content, senderid, sender, targets)
            for id, title, content, school, senderid, sender in execute_sql(
                'SELECT notice.id, notice.title, notice.content, notice.school, user.userid, user.username '
                'FROM notice '
                'JOIN user ON user.userid = notice.sender '
                'WHERE {} '
                'ORDER BY notice.id DESC'.format(
                    'TRUE' if Permission.ADMIN.authorized() else 'notice.sender = :sender'
                ),
                sender=session.get('userid')
            )
            if (targets := list(enumerate(execute_sql(
                'SELECT user.userid, user.username '
                'FROM user_notice AS un '
                'JOIN user ON user.userid = un.userid '
                'WHERE noticeid = :noticeid',
                noticeid=id
            ))) if not school else None) or True
        ]
    )

@route(Management, url.edit_notices)
@login_required
@permission(Permission.MANAGER)
@view
def edit_notices_post(noticeid: int, title: str, content: str, targets: list[str]):
    if execute_sql('SELECT id FROM notice WHERE id = :id', id=noticeid).fetchone() is None:
        return render_template('zvms/error.html', msg='通知不存在')
    if targets:
        try:
            userids = username2userid(targets)
        except ValueError as exn:
            return render_template('zvms/error.html', msg='用户{}不存在'.format(exn.args[0]))
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
    return redirect('/management/edit-notices')

@route(Management, url.delete_notice)
@login_required
@permission(Permission.MANAGER)
@view
def delete_notice(noticeid: int):
    if execute_sql('SELECT id FROM notice WHERE id = :id', id=noticeid).fetchone() is None:
        return render_template('zvms/error.html', msg='通知不存在')
    execute_sql('DELETE FROM notice WHERE id = :id', id=noticeid)
    return redirect('/management/edit-notices')