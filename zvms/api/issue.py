from typing import TypedDict

from flask import Blueprint

from ..framework import (
    lengthedstr,
    api_login_required,
    permission,
    api_route,
    url
)
from ..util import dump_objects
from ..misc import Permission
from ..kernel import issue as IssueKernel

Issue = Blueprint('Issue', __name__, url_prefix='/issue')


class IssueInfo(TypedDict):
    authorId: int
    authorName: str
    content: str
    time: str


@api_route(Issue, url.list, 'GET')
@api_login_required
@permission(Permission.MANAGER)
def list_issues() -> list[IssueInfo]:
    """列出所有的反馈"""
    return dump_objects(IssueKernel.list_issues(), IssueInfo)


class IssueTimeAndContent(TypedDict):
    time: str
    content: str


class MyIssues(TypedDict):
    today: int
    total: list[IssueTimeAndContent]


@api_route(Issue, url.me, 'GET')
@api_login_required
def my_issues() -> MyIssues:
    """
列出自己提交的反馈  
`today`字段是当天提交的反馈数量. 一天最多只能提交五条
    """
    issues_today, issues_posted = IssueKernel.my_issues()
    return {
        'today': issues_today,
        'total': dump_objects(issues_posted, IssueTimeAndContent)
    }


@api_route(Issue, url.post)
@api_login_required
def post_issue(content: lengthedstr[64]) -> None:
    """提交一条反馈"""
    IssueKernel.post_issue(content)
