from flask import (
    Blueprint,
    redirect,
    request,
    session
)

from ..util import (
    render_template,
    render_markdown,
    execute_sql,
    md5
)
from ..framework import (
    login_required,
    zvms_route,
    url
)
from ..kernel import notice as NoticeKernel
from ..kernel import user as UserKernel
from ..misc import Permission

User = Blueprint('User', __name__, url_prefix='/user')


@zvms_route(User, url.login, 'GET')
def login_get():
    if 'userid' in session:
        return redirect(f'/user/{session.get("userid")}')
    return render_template('zvms/login.html')


@zvms_route(User, url.login)
def login_post(userident: str, password: str):
    info = UserKernel.login(userident, md5(password.encode()))
    session.update(dict(zip(
        ('userid', 'username', 'permission', 'classid'),
        info
    )))
    return redirect(request.args.get('redirect_to', f'/user/{info[0]}'))


@zvms_route(User, url.logout, 'GET')
def logout():
    session.clear()
    return redirect('/user/login')


@zvms_route(User, url['userid'], 'GET')
@login_required
def user_info(userid: int):
    manager = int(session.get('permission')) & (
        Permission.MANAGER | Permission.ADMIN)
    username, permission, classid, class_name = UserKernel.user_info(userid)
    notices = NoticeKernel.my_notices()
    return render_template(
        'zvms/user.html',
        userid=userid,
        username=username,
        permission=str(Permission(permission)),
        classid=classid,
        class_name=class_name,
        scores=UserKernel.get_time_sums(userid),
        is_self=userid == session.get('userid'),
        notices=[
            (i, title, render_markdown(content), *spam)
            for i, (title, content, *spam) in enumerate(notices)
        ],
        manager=manager
    )


@zvms_route(User, url.modify_password)
@login_required
def modify_password(target: int, old: str, new: str):
    UserKernel.modify_password(target, md5(old.encode()), md5(new.encode()))
    return render_template('zvms/success.html', msg='修改密码成功')


@zvms_route(User, url('class').list, 'GET')
@login_required
def class_list():
    return render_template(
        'zvms/class_list.html',
        classes=execute_sql('SELECT id, name FROM class').fetchall()
    )


@zvms_route(User, url('class')['classid'], 'GET')
@login_required
def class_info(classid: int):
    name, members = UserKernel.class_info(classid)
    return render_template(
        'zvms/class.html',
        name=name,
        members=members
    )
