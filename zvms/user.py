from flask import (
    Blueprint, 
    redirect, 
    abort,
    request, 
    session
)

from .util import (
    execute_sql, 
    render_template, 
    get_user_scores, 
    render_markdown,
    md5
)
from .framework import route, url, view, login_required
from .misc import Permission

User = Blueprint('User', __name__, url_prefix='/user')

@User.route('/login')
@view
def login_get():
    if 'userid' in session:
        return redirect('/user/{}'.format(session.get('userid')))
    return render_template('zvms/login.html')

@route(User, url.login)
@view
def login_post(userident: str, password: str):
    user_info = execute_sql(
        'SELECT userid, username, permission, classid '
        'FROM user '
        'WHERE {} = :userident AND password = :password'.format(
            'userid' if userident.isdecimal() else 'username'
        ),
        userident=userident,
        password=md5(password.encode())
    ).fetchone()
    if user_info is None:
        return render_template('zvms/error.html', msg='用户名或密码错误')
    session.update(dict(zip(
        ('userid', 'username', 'permission', 'classid'),
        user_info
    )))
    return redirect(request.args.get('redirect_to', '/user/{}'.format(user_info[0])))

@User.route('/logout')
@view
def logout():
    session.clear()
    return redirect('/user/login')

@User.route('/<int:id>')
@login_required
@view
def user_info(id: int):
    manager = int(session.get('permission')) & (Permission.MANAGER | Permission.ADMIN)
    match execute_sql(
        'SELECT user.username, user.permission, user.classid, class.name '
        'FROM user '
        'JOIN class ON class.id = user.classid '
        'WHERE userid = :userid ',
        userid=id,
    ).fetchone():
        case None:
            abort(404)
        case [username, permission, classid, class_name]: ...
    notices = execute_sql(
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
    return render_template(
        'zvms/user.html', 
        userid=id,
        username=username,
        permission=str(Permission(permission)),
        classid=classid,
        class_name=class_name,
        scores=get_user_scores(id),
        is_self=id == session.get('userid'),
        notices=[
            (i, title, render_markdown(content), *spam)
            for i, (title, content, *spam) in enumerate(notices)
        ],
        manager=manager
    )

@route(User, url.modify_password)
@login_required
@view
def modify_password(target: int, old: str, new: str):
    manager = Permission.MANAGER.authorized()
    if target != int(session.get('userid')) and not manager:
        return render_template('zvms/error.html', msg='权限不足')
    match execute_sql(
        'SELECT permission FROM user WHERE userid = :userid', 
        userid=target
    ).fetchone():
        case None:
            return render_template('zvms/error.html', msg='用户不存在')
        case [perm] if perm & Permission.ADMIN and not manager:
            return render_template('zvms/error.html', msg='权限不足')
    if not manager and execute_sql(
        'SELECT * FROM user WHERE userid = :userid AND password = :password',
        userid=target,
        password=md5(old.encode())
    ):
        return render_template('zvms/error.html', msg='旧密码错误')
    execute_sql(
        'UPDATE user '
        'SET password = :password '
        'WHERE userid = :userid',
        userid=target,
        password=md5(new.encode())
    )
    return render_template('zvms/success.html', msg='修改密码成功')

@User.route('/class/list')
@login_required
@view
def class_list():
    return render_template(
        'zvms/class_list.html',
        classes=execute_sql('SELECT id, name FROM class').fetchall()
    )

@User.route('/class/<int:id>')
@login_required
@view
def class_info(id: int):
    name = execute_sql(
        'SELECT name FROM class '
        'WHERE id = :id',
        id=id
    ).fetchone()
    if name is None:
        abort(404)
    return render_template(
        'zvms/class.html',
        name=name[0],
        members=execute_sql(
            'SELECT userid, username '
            'FROM user '
            'WHERE classid = :classid',
            classid=id
        ).fetchall()
    )