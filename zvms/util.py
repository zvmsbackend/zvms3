from datetime import datetime, date
import hashlib
import re

from flask import session, render_template as _render_template
from mistune import Markdown, HTMLRenderer
from sqlalchemy.sql import text
from sqlalchemy import Result

from .misc import db, Permission
from .framework import ZvmsError

def execute_sql(sql: str, **kwargs) -> Result:
    return db.session.execute(text(sql), kwargs)

def md5(s: bytes) -> str:
    md5 = hashlib.md5()
    md5.update(s)
    return md5.hexdigest()

def inexact_now() -> datetime:
    return datetime.now().replace(microsecond=0)

def username2userid(usernames: list[str]) -> list[int]:
    ret = []
    for username in usernames:
        match execute_sql(
            'SELECT userid '
            'FROM user WHERE {} = :username'.format(
                'userid' if username.isdecimal() else 'username'
            ),
            username=username
        ).fetchone():
            case None:
                raise ZvmsError('用户{}不存在'.format(username))
            case [id]:
                ret.append(id)
    return ret

def get_primary_key():
    return execute_sql('SELECT LAST_INSERT_ROWID()').fetchone()

def render_template(template_name: str, **context):
    return _render_template(
        template_name,
        **context,
        _year=datetime.now().year,
        _login='userid' in session,
        _userid=session.get('userid'),
        _permission=session.get('permission'),
        Permission=Permission
    )

markdown = Markdown(HTMLRenderer())

def render_markdown(content: str) -> str:
    return re.sub(
        r'href="[^/].+?"', 'href="#"', 
        re.sub(r'src=".+"', '', markdown.parse(content))
    )

def get_user_scores(userid: int) -> dict[int, int]:
    return dict(execute_sql(
        'SELECT vol.type, SUM(uv.reward) '
        'FROM user_vol AS uv '
        'JOIN volunteer AS vol ON vol.id = uv.volid '
        'WHERE uv.userid = :userid AND uv.status = 5 '
        'GROUP BY vol.type',
        userid=userid
    ).fetchall())

def three_days_after():
    today = date.today()
    return today.replace(day=today.day + 3)

def send_notice_to(title: str, content: str, target: int, class_notice: bool = False) -> None:
    execute_sql(
        'INSERT INTO notice(title, content, sender, school, expire) '
        'VALUES(:title, :content, 0, FALSE, :expire)',
        title=title,
        content=content,
        expire=three_days_after()
    )
    noticeid = get_primary_key()[0]
    execute_sql(
        'INSERT INTO {}({}, noticeid) '
        'VALUES(:target, :noticeid)'.format(
            'class_notice' if class_notice else 'user_notice',
            'classid' if class_notice else 'userid'
        ),
        target=target,
        noticeid=noticeid
    )