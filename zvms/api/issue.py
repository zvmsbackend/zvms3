from flask import Blueprint, session

from ..framework import (
    lengthedstr,
    ZvmsError,
    login_required,
    permission,
    api_route,
    url
)
from ..misc import Permission, ErrorCode
from ..util import execute_sql, dump_object, inexact_now

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


@api_route(Issue, url.list, 'GET')
@login_required
@permission(Permission.MANAGER)
def list_issues():
    """列出所有的反馈"""
    return dump_object(Api.list_issues(), ['authorId', 'authorName', 'content', 'time'])


@api_route(Issue, url.me, 'GET')
@login_required
def my_issues():
    """
    列出自己提交的反馈  
    `today`字段是当天提交的反馈数量. 一天最多只能提交五条
    """
    issues_today, issues_posted = Api.my_issues()
    return {
        'today': issues_today,
        'total': dump_object(issues_posted, ['time', 'content'])
    }


@api_route(Issue, url.post)
@login_required
def post_issue(content: lengthedstr[64]):
    """提交一条反馈"""
    Api.post_issue(content)
