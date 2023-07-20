from datetime import date

from flask import (
    Blueprint, 
    redirect, 
    request, 
    session
)

from .util import (
    execute_sql, 
    inexact_now, 
    render_template
)
from .framework import (
    lengthedstr,
    route,
    view,
    url
)

About = Blueprint('About', __name__)

@About.route('/about')
@view
def index():
    issues_posted = None
    issues_today = 0
    if 'userid' in session:
        issues_posted = execute_sql(
            'SELECT time, content '
            'FROM issue '
            'WHERE author = :author',
            author=session.get('userid')
        ).fetchall()
        issues_today = execute_sql(
            'SELECT COUNT(*) '
            'FROM issue '
            'WHERE author = :author AND time > :today',
            author=session.get('userid'),
            today=date.today()
        ).fetchone()[0]
    return render_template(
        'zvms/about.html',
        issues_posted=issues_posted,
        issues_today=issues_today
    )

@route(About, url.issue)
@view
def issue(content: lengthedstr[64]):
    times = execute_sql(
        'SELECT COUNT(*) '
        'FROM issue '
        'WHERE author = :id AND time > :today',
        id=session.get('userid'),
        today=date.today()
    ).fetchone()[0]
    if times >= 5:
        return render_template('zvms/error.html', msg='反馈已达上限')
    execute_sql(
        'INSERT INTO issue(author, content, time) '
        'VALUES(:author, :content, :time)',
        author=session.get('userid'), 
        content=content,
        time=inexact_now()
    )
    return redirect(request.referrer)