from enum import IntEnum, IntFlag
import logging

from flask_sqlalchemy import SQLAlchemy
from flask import session

logger = logging.getLogger()
logging.basicConfig(
    level=logging.INFO
)

db = SQLAlchemy()

_empty = object()


class ZvmsEnum(IntEnum):
    def __str__(self) -> str:
        return self.__class__.__tostr__[self - 1]


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

    def authorized(self, /, that=_empty, *, admin: bool = True) -> bool:
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


class VolStatus(ZvmsEnum):
    UNAUDITED = 1
    ACCEPTED = 2
    REJECTED = 3
    SPECIAL = 4

    __tostr__ = ['未过审', '已通过', '不可报名', '特殊义工']

    def badge(self) -> str:
        return ('dark', 'success', 'danger', 'primary')[self - 1]


class VolType(ZvmsEnum):
    INSIDE = 1
    OUTSIDE = 2
    LARGE = 3

    __tostr__ = ['校内义工', '校外义工', '社会实践']
    

class VolKind(ZvmsEnum):
    INSIDE = 1
    APPOINTED = 2
    SPECIAL = 3

    __tostr__ = ['校内', '指定', '特殊']


class ThoughtStatus(ZvmsEnum):
    WAITING_FOR_SIGNUP_AUDIT = 1
    DRAFT = 2
    WAITING_FOR_FIRST_AUDIT = 3
    WAITING_FOR_FINAL_AUDIT = 4
    ACCEPTED = 5
    REJECTED = 6
    SPIKE = 7

    __tostr__ = [
        '等待报名审核',
        '草稿',
        '等待初审',
        '等待终审',
        '接受',
        '拒绝',
        '打回'
    ]

    def badge(self) -> str:
        return ('dark', 'secondary', 'info', 'primary', 'success', 'danger', 'warning')[self - 1]


class ErrorCode(ZvmsEnum):
    NO_ERROR = 1
    LOGIN_REQUIRED = 2
    VALIDATION_FAILS = 3
    NOT_AUTHORIZED = 4
    ISSUES_LIMIT_EXCEEDED = 5
    NOTICE_NOT_EXISTS = 6
    USER_NOT_EXISTS = 7
    INCORRECT_USERNAME_OR_PASSWORD = 8
    INCORRECT_OLD_PASSWORD = 9
    CLASS_OVERFLOW = 10
    CANT_AUDIT_VOLUNTEER = 11
    CANT_SIGNUP_FOR_VOLUNTEER = 12
    SIGNUP_NOT_EXISTS = 13
    CANT_ROLLBACK_OTHERS_SIGNUP = 14
    CANT_DELETE_OTHERS_VOLUNTEER = 15
    CANT_MODIFY_OTHERS_VOLUNTEER = 16
    CANT_AUDIT_REJECTED_VOLUNTEER = 17
    VOLUNTEER_KIND_MISMATCH = 18
    CANT_MODIFY_REJECTED_VOLUNTEER = 19
    CANT_EDIT_OTHERS_THOUGHT = 20
    THOUGHT_NOT_EDITABLE = 21
    PICTURE_NOT_EXISTS = 22
    FILE_DECODE_FAILS = 23
    THOUGHT_NOT_AUDITABLE = 24
    INVALID_IMAGE_FILE = 25

    __tostr__ = [
        '无错误',
        '未登录',
        '参数校验错误: {expected!r} expected, {found!r} found [{where}]',
        '权限不足',
        '反馈已达上限',
        '通知{noticeid}不存在',
        '用户{userid}不存在',
        '用户名或密码错误',
        '旧密码错误',
        '班级{classid}人数溢出',
        '该义工不可审核',
        '该义工不可报名',
        '报名不存在',
        '不能撤回他人的报名',
        '不能删除他人的义工',
        '不能修改他人的义工',
        '不能修改被拒绝的义工',
        '义工种类错误',
        '不能修改被拒绝的义工',
        '不能修改他人的感想',
        '感想不可编辑',
        '图片{filename}不存在',
        '文件{filename}解码失败',
        '感想不可审核',
        '非法图片文件'
    ]
