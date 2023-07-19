import logging
from enum import IntEnum, IntFlag

from flask_sqlalchemy import SQLAlchemy
from flask import session

logger = logging.getLogger()
logging.basicConfig(
    level=logging.INFO
)

db = SQLAlchemy()

_empty = object()

class Permission(IntFlag):
    CLASS = 1
    MANAGER = 2
    AUDITOR = 4
    INSPECTOR = 8
    ADMIN = 16

    def __str__(self) -> str:
        ret = []
        for value, name in permission2str.items():
            if self & value:
                ret.append(name)
                self -= value
        return ', '.join(ret)
    
    def authorized(self, /, that = _empty, *, admin: bool = True) -> bool:
        if that is _empty:
            that = int(session.get('permission'))
        if that is None:
            return False
        return bool(((self | Permission.ADMIN) if admin else self) & that)
    
permission2str = {
    Permission.CLASS: '班级',
    Permission.MANAGER: '管理员',
    Permission.AUDITOR: '审计员',
    Permission.INSPECTOR: '督察员',
    Permission.ADMIN: 'Administrator'
}

class VolStatus(IntEnum):
    UNAUDITED = 1
    ACCEPTED = 2
    REJECTED = 3
    SPECIAL = 4

    def __str__(self) -> str:
        return ('未过审', '可报名', '不可报名', '特殊义工')[self - 1]
    
    def badge(self) -> str:
        return ('dark', 'success', 'danger', 'primary')[self - 1]

class VolType(IntEnum):
    INSIDE = 1
    OUTSIDE = 2
    LARGE = 3

    def __str__(self) -> str:
        return ('校内义工', '校外义工', '社会实践')[self - 1]
    
class ThoughtStatus(IntEnum):
    WAITING_FOR_SIGNUP_AUDIT = 1
    DRAFT = 2
    WAITING_FOR_FIRST_AUDIT = 3
    WAITING_FOR_FINAL_AUDIT = 4
    ACCEPTED = 5
    REJECTED = 6
    PITCHBACK = 7

    def __str__(self) -> str:
        return (
            '等待报名审核',
            '草稿',
            '等待初审',
            '等待终审',
            '接受',
            '拒绝',
            '打回'
        )[self - 1]
    
    def badge(self) -> str:
        return ('dark', 'secondary', 'info', 'primary', 'success', 'danger', 'warning')[self - 1]