from flask import (
    Blueprint,
    redirect,
    request,
    session
)

from ..util import render_template
from ..framework import (
    lengthedstr,
    login_required,
    zvms_route,
    url
)
from ..kernel import issue as IssueKernel

About = Blueprint('About', __name__)


@zvms_route(About, url.about, 'GET')
def index():
    issues_posted = None
    issues_today = 0
    if 'userid' in session:
        issues_today, issues_posted = IssueKernel.my_issues()
    return render_template(
        'zvms/about.html',
        issues_posted=issues_posted,
        issues_today=issues_today
    )


@zvms_route(About, url.issue)
@login_required
def issue(content: lengthedstr[64]):
    IssueKernel.post_issue(content)
    return redirect(request.referrer)