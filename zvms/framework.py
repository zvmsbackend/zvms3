from typing import Callable, _LiteralGenericAlias
from abc import ABCMeta, abstractmethod
from inspect import signature, _empty
from types import GenericAlias
from urllib.parse import quote
from functools import wraps
from datetime import date
from enum import EnumType

from werkzeug.datastructures import ImmutableMultiDict, FileStorage
from flask import Blueprint, session, request, redirect, abort
from werkzeug.exceptions import NotFound

from .misc import db, logger, Permission

class Validator(metaclass=ABCMeta):
    @abstractmethod
    def validate(self, /, arg: str | list[str]): ...

    @abstractmethod
    def errormsg(self) -> str: ...

    def from_files(self) -> bool:
        return False

    method = ImmutableMultiDict.get
    accept_none = False

class IntegerValidator(Validator):
    def validate(self, /, arg: str):
        if arg.isdecimal():
            return int(arg)
        return None
    
    def errormsg(self) -> str:
        return '应为整数'

integer = IntegerValidator()

class DateValidator(Validator):
    def validate(self, /, arg: str):
        try:
            d = date.fromisoformat(arg)
            if d < date.today():
                return None
            return d
        except ValueError:
            return None
        
    def errormsg(self) -> str:
        return '应为日期'

isodate = DateValidator()

class LengthValidator(Validator):
    def __init__(self, /, max: int) -> None:
        self.max = max

    def validate(self, /, arg: str):
        if len(arg) > self.max:
            return None
        return arg
    
    def errormsg(self) -> str:
        return f'长度不应超过{self.max}'
    
class lengthedstr(str):
    def __class_getitem__(self, length: int) -> LengthValidator:
        return LengthValidator(length)
    
class BoolValidator(Validator):
    def validate(self, /, arg: str | list[str]):
        return bool(arg)
    
    def errormsg(self) -> str:
        return '应为布尔值'

    accept_none = True

boolean = BoolValidator()
    
class AnyValidator(Validator):
    def validate(cls, /, arg: str):
        return arg
    
    def errormsg(self) -> str:
        return ''
    
any = AnyValidator()

class ListValidator(Validator):
    def __init__(self, /, child_validator: Validator, required: bool) -> None:
        self.child_validator = child_validator
        self.required = required

    def validate(self, /, arg: list[str]):
        if not arg and self.required:
            return None
        ret = []
        for i in arg:
            tmp = self.child_validator.validate(i)
            if tmp is None:
                return None
            ret.append(tmp)
        if len(ret) != len(set(ret)):
            return None
        return ret
    
    def errormsg(self) -> str:
        return '应为列表'
    
    def from_files(self) -> bool:
        return self.child_validator.from_files()
    
    method = ImmutableMultiDict.getlist

class requiredlist(list):
    def __class_getitem__(cls, /, child_validator: type) -> ListValidator:
        return ListValidator(annotation2validator(child_validator), True)

class EnumValidator(Validator):
    def __init__(self, /, enum: EnumType) -> None:
        self.enum = enum

    def validate(self, /, arg: str):
        if not arg.isnumeric():
            return None
        arg = int(arg)
        if arg not in self.enum._value2member_map_:
            return None
        return self.enum(arg)
    
    def errormsg(self) -> str:
        return '取值应为{}中的一个'.format(', '.join(map(str, self.enum._value2member_map_)))
    
class LiteralValidator(Validator):
    def __init__(self, /, choices) -> None:
        self.choices = choices

    def validate(self, /, arg: str | list[str]):
        if arg in self.choices:
            return arg
        if arg.isnumeric():
            numeric = int(arg)
            for choice in self.choices:
                try:
                    if choice.__class__(numeric) == choice:
                        return choice
                except (ValueError, TypeError): ...
        return None
    
    def errormsg(self) -> str:
        return '取值应为{}中的一个'.format(', '.join(map(str, self.choices)))
    
class DefaultValidator(Validator):
    def __init__(self, /, child_validator: Validator, default_value) -> None:
        self.child_validator = child_validator
        self.default_value = default_value

    def validate(self, /, arg: str | list[str]):
        if arg is None:
            return self.default_value
        return self.child_validator.validate(arg)
    
    def errormsg(self) -> str:
        return self.child_validator.errormsg()
    
    def from_files(self) -> bool:
        return self.child_validator.from_files()
    
    accept_none = True

class FileValidator(Validator):
    def validate(self, /, arg: str | list[str]):
        return arg
    
    def errormsg(self) -> str:
        return ''

    def from_files(self) -> bool:
        return True
    
file = FileValidator()

class Url:
    def __init__(self, /, string: str = '', params: frozenset = frozenset()) -> None:
        self.string = string
        self.params = params

    def __getattr__(self, /, attr: str) -> 'Url':
        return Url(self.string + '/' + attr.replace('_', '-'), self.params)
    
    def __getitem__(self, /, index: str) -> 'Url':
        return Url('{}/<int:{}>'.format(self.string, index), self.params | frozenset([index]))
    
    def root(self = None) -> 'Url':
        return Url('/')
    
url = Url()

class ZvmsError(Exception): ...

def annotation2validator(annotation: type | Validator, default = _empty) -> Validator:
    if isinstance(annotation, Validator):
        return annotation
    ret = EnumValidator(annotation) if isinstance(annotation, EnumType) else {
        bool: boolean,
        str: any,
        date: isodate,
        int: integer,
        FileStorage: file
    }.get(
        annotation, 
        ((lambda: ListValidator(annotation2validator(annotation.__args__[0], _empty), False))
        if isinstance(annotation, GenericAlias) else 
        (lambda: LiteralValidator(annotation.__args__))
        if isinstance(annotation, _LiteralGenericAlias)
        else (lambda: any))()
    )
    if default is _empty:
        return ret
    return DefaultValidator(ret, default)

def route(blueprint: Blueprint, url: Url, method: str = 'POST') -> Callable[[Callable], Callable]:
    def deco(fn: Callable) -> Callable:
        form_params = {
            name: annotation2validator(param.annotation, param.default)
            for name, param in signature(fn).parameters.items()
            if name not in url.params
        }
        @wraps(fn)
        def wrapper(*args, **kwargs):
            args_dict = request.form if method == 'POST' else request.args
            form_args = {}
            for k, v in form_params.items():
                d = request.files if v.from_files() else args_dict
                arg = v.__class__.method(d, k)
                if arg is None and not v.__class__.accept_none:
                    from .util import render_template
                    return render_template(
                        'zvms/error.html',
                        msg='表单校验错误: 缺少{}'.format(k)
                    )
                arg = v.validate(arg)
                if arg is None:
                    from .util import render_template
                    return render_template(
                        'zvms/error.html',
                        msg='表单校验错误: {} {}'.format(k, v.errormsg())
                    )
                form_args[k] = arg
            return fn(*args, **kwargs, **form_args)
        blueprint.add_url_rule(
            url.string,
            view_func=wrapper,
            methods=[method]
        )
        return wrapper
    return deco
    
def view(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            ret = fn(*args, **kwargs)
            db.session.commit()
            return ret
        except NotFound:
            raise
        except Exception as exn:
            db.session.rollback()
            logger.exception(exn)
            from .util import render_template
            return render_template(
                'zvms/error.html', 
                msg=exn.args[0] if isinstance(exn, ZvmsError)
                else '服务器遇到了{}错误'.format(exn.__class__.__qualname__)
            )
    return wrapper

def login_required(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'userid' not in session:
            return redirect('/user/login?redirect_to=' + quote(request.url))
        return fn(*args, **kwargs)
    return wrapper

def permission(perm: Permission) -> Callable[[Callable], Callable]:
    def deco(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if int(session.get('permission')) & (perm | Permission.ADMIN):
                return fn(*args, **kwargs)
            abort(403)
        return wrapper
    return deco