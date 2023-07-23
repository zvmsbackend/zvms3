from typing import TypedDict

from flask import Blueprint, session

from ..framework import (
    lengthedstr,
    ZvmsError,
    login_required,
    permission,
    api_route,
    url
)
from ..util import execute_sql, dump_objects, inexact_now
from ..misc import Permission

Issue = Blueprint('Issue', __name__, url_prefix='/issue')


class Api:
    @staticmethod
    def list_issues() -> list[tuple[int, str, str, str]]:
        return execute_sql(
            'SELECT issue.author, user.username, issue.content, issue.time '
            'FROM issue '
            'JOIN user ON issue.author = user.userid '
            'ORDER BY issue.id DESC'
        ).fetchall()

    @staticmethod
    def my_issues() -> tuple[int, list[tuple[str, str]]]:
        issues_posted = execute_sql(
            'SELECT time, content '
            'FROM issue '
            'WHERE author = :author',
            author=session.get('userid')
        ).fetchall()
        issues_today = execute_sql(
            'SELECT COUNT(*) '
            'FROM issue '
            'WHERE author = :author AND time > DATE("NOW")',
            author=session.get('userid')
        ).fetchone()[0]
        return issues_today, issues_posted

    @staticmethod
    def post_issue(content: str) -> None:
        times = execute_sql(
            'SELECT COUNT(*) '
            'FROM issue '
            'WHERE author = :id AND time > DATE("NOW")',
            id=session.get('userid'),
        ).fetchone()[0]
        if times >= 5:
            raise ZvmsError('反馈已达上限')
        execute_sql(
            'INSERT INTO issue(author, content, time) '
            'VALUES(:author, :content, :time)',
            author=session.get('userid'),
            content=content,
            time=inexact_now()
        )


class IssueInfo(TypedDict):
    authorId: int
    authorName: str
    content: str
    time: str


@api_route(Issue, url.list, 'GET')
@login_required
@permission(Permission.MANAGER)
def list_issues() -> list[IssueInfo]:
    """列出所有的反馈"""
    return dump_objects(Api.list_issues(), IssueInfo)


class IssueTimeAndContent(TypedDict):
    time: str
    content: str


class MyIssues(TypedDict):
    today: int
    total: list[IssueTimeAndContent]


@api_route(Issue, url.me, 'GET')
@login_required
def my_issues() -> MyIssues:
    """
列出自己提交的反馈  
`today`字段是当天提交的反馈数量. 一天最多只能提交五条
    """
    issues_today, issues_posted = Api.my_issues()
    return {
        'today': issues_today,
        'total': dump_objects(issues_posted, IssueTimeAndContent)
    }


@api_route(Issue, url.post)
@login_required
def post_issue(content: lengthedstr[64]) -> None:
    """提交一条反馈"""
    Api.post_issue(content)
