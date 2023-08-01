from typing import (
    _TypedDictMeta,
    TypeAlias,
    Callable,
    Literal,
    _LiteralGenericAlias
)
from types import GenericAlias, MappingProxyType
from abc import ABCMeta, abstractmethod
from contextlib import contextmanager
from inspect import signature, _empty
from urllib.parse import quote
from functools import partial
from functools import wraps
from datetime import date
from enum import EnumType
from typing import Any
import json

from flask import Blueprint, Response, session, request, redirect, abort
from werkzeug.datastructures import ImmutableMultiDict, FileStorage
from werkzeug.exceptions import NotFound, Forbidden

from .misc import db, logger, Permission, ErrorCode


class Validator(metaclass=ABCMeta):
    def validate(self, /, arg: Any) -> Any:
        if not isinstance(arg, self._validate.__annotations__.get('arg')):
            print(self, arg, self._validate.__annotations__.get('arg'))
            Validator.error(self, arg)
        return self._validate(arg)

    @abstractmethod
    def _validate(self, /, arg: Any) -> Any: ...

    @abstractmethod
    def as_json(self) -> Any: ...

    def from_files(self) -> bool:
        return False

    where = []

    @contextmanager
    @staticmethod
    def path(s: str):
        Validator.where.append(s)
        yield
        Validator.where.pop()

    @staticmethod
    def error(expected: 'Validator', found: Any) -> None:
        where = '.'.join(Validator.where)
        Validator.where.clear()
        info = {
            'where': where,
            'expected': expected.as_json(),
            'found': found
        }
        logger.warn(info)
        raise ZvmsError(ErrorCode.VALIDATION_FAILS, info)


class BoolValidator(Validator):
    def _validate(self, /, arg: bool) -> bool:
        return arg

    def as_json(self) -> Any:
        return 'boolean'


boolean = BoolValidator()


class IntValidator(Validator):
    def _validate(self, /, arg: int) -> int:
        if not isinstance(arg, int):
            Validator.error(self, arg)
        if arg < 0 or arg > 0x7fffffff:
            Validator.error(self, arg)
        return arg

    def as_json(self) -> Any:
        return 'integer'


class IntStringValidator(IntValidator):
    def _validate(self, /, arg: str) -> int:
        if not arg.isdecimal():
            Validator.error(self, arg)
        return super()._validate(int(arg))


sint = IntStringValidator()
integer = IntValidator()


class DateValidator(Validator):
    def _validate(self, /, arg: str) -> date:
        try:
            d = date.fromisoformat(arg)
            if d < date.today():
                Validator.error(self, arg)
            return d
        except ValueError:
            Validator.error(self, arg)

    def as_json(self) -> str:
        return 'date'


isodate = DateValidator()


class StringValidator(Validator):
    def __init__(self, /, min: int, max: int) -> None:
        self.min = min
        self.max = max

    def _validate(self, /, arg: str) -> str:
        if self.min <= len(arg) <= self.max:
            return arg
        Validator.error(self, arg)

    def as_json(self) -> Any:
        return {'__string__': True, 'length': [self.min, self.max]}


class _StringValidatorMaker:
    def __init__(self, /, min: int, max: int) -> None:
        self.min = min
        self.max = max


class lengthedstr(str):
    def __class_getitem__(self, length: int | tuple[int, int]) -> _StringValidatorMaker:
        match length:
            case [min, max]:
                return _StringValidatorMaker(min, max)
            case _:
                return _StringValidatorMaker(0, length)


class BoolStringValidator(Validator):
    def _validate(self, /, arg: str | None) -> bool:
        return bool(arg)

    def as_json(self) -> Any:
        return 'boolean'


sbool = BoolStringValidator()


class DynamicValidator(Validator):
    def _validate(self, /, arg: Any) -> Any:
        return arg

    def as_json(self) -> Any:
        return 'any'


dynamic = DynamicValidator()


class ListValidator(Validator):
    def __init__(self, /, child_validator: Validator, required: bool, unique: bool) -> None:
        self.child_validator = child_validator
        self.required = required
        self.unique = unique

    def _validate(self, /, arg: list) -> list:
        if not arg and self.required:
            Validator.error(self, arg)
        ret = []
        for i, item in enumerate(arg):
            with Validator.path(f'[{i}]'):
                ret.append(self.child_validator.validate(item))
        if self.unique and len(ret) != sum(1 for i, x in enumerate(ret) if x not in ret[:i]):
            Validator.error(self, arg)
        return ret

    def as_json(self) -> Any:
        return [self.child_validator.as_json()] + (['required'] if self.required else []) + (['unique'] if self.unique else [])

    def from_files(self) -> bool:
        return self.child_validator.from_files()


class _ListValidatorMaker:
    def __init__(self, /, generic_argument: type, required: bool, unique: bool) -> None:
        self.generic_argument = generic_argument
        self.required = required
        self.unique = unique


class metalist(list):
    def __class_getitem__(cls, /, args: tuple) -> object:
        return _ListValidatorMaker(args[0], 'required' in args, 'duplicate' not in args)


class ObjectValidator(Validator):
    def __init__(self, fields: dict[str, Validator]) -> None:
        self.fields = fields

    def _validate(self, /, arg: dict) -> dict:
        ret = {}
        for k, v in self.fields.items():
            with Validator.path(k):
                _arg = request.files if v.from_files() else arg
                if isinstance(_arg, ImmutableMultiDict) and isinstance(v, ListValidator):
                    ret[k] = v.validate(_arg.getlist(k))
                else:
                    ret[k] = v.validate(_arg.get(k))
        return ret

    def as_json(self):
        return {k: v.as_json() for k, v in self.fields.items()}


class EnumValidator(Validator):
    def __init__(self, /, enum: EnumType) -> None:
        self.enum = enum

    def _validate(self, /, arg: object) -> Any:
        if arg not in self.enum._value2member_map_:
            Validator.error(self, arg)
        return self.enum(arg)

    def as_json(self) -> Any:
        return self.enum.__name__


class EnumStringValidator(EnumValidator):
    def _validate(self, /, arg: str) -> Any:
        if not arg.isdecimal():
            Validator.error(self, arg)
        return super()._validate(int(arg))


class LiteralValidator(Validator):
    def __init__(self, /, choices: list[Any]) -> None:
        self.choices = choices

    def _validate(self, /, arg: object) -> Any:
        if arg in self.choices:
            return arg
        Validator.error(self, arg)

    def as_json(self) -> Any:
        return {'__literal__': True, 'choices': self.choices}


class LiteralStringValidator(LiteralValidator):
    def _validate(self, /, arg: str) -> Any:
        if arg in self.choices:
            return arg
        if arg.isdecimal():
            numeric = int(arg)
            for choice in self.choices:
                try:
                    if choice.__class__(numeric) == choice:
                        return choice
                except (ValueError, TypeError):
                    ...
        Validator.error(self, arg)


class DefaultValidator(Validator):
    def __init__(self, /, child_validator: Validator, default_value) -> None:
        self.child_validator = child_validator
        self.default_value = default_value

    def _validate(self, /, arg: object) -> Any:
        if arg is None:
            return self.default_value
        return self.child_validator.validate(arg)

    def as_json(self) -> Any:
        return {'__default__': True, 'child': self.child_validator.as_json(), 'value': self.default_value}

    def from_files(self) -> bool:
        return self.child_validator.from_files()


class FileValidator(Validator):
    def _validate(self, /, arg: FileStorage) -> FileStorage:
        return arg

    def as_json(self) -> Any:
        return 'file'

    def from_files(self) -> bool:
        return True


file = FileValidator()


class Url:
    def __init__(self, /, string: str = '', params: dict = MappingProxyType({})) -> None:
        self.string = string
        self.params = params

    def __call__(self, string: str) -> 'Url':
        return Url(self.string + '/' + string.replace('_', '-'), self.params)

    def __getattr__(self, attr: str) -> 'Url':
        return self(attr)

    def __getitem__(self, index: str | tuple[str, Any]) -> 'Url':
        match index:
            case str():
                string = f'<int:{index}>'
                t = 'number'
            case [index, 'string' as t]:
                string = f'<{index}>'
        return Url(
            f'{self.string}/{string}',
            MappingProxyType(self.params | {index: t})
        )


url = Url()


class ZvmsError(Exception):
    ...


RouteMode: TypeAlias = Literal['json', 'zvms', 'toolkit']


def annotation2validator(annotation: type | Validator, mode: RouteMode, default: Any) -> Validator:
    match annotation:
        case _StringValidatorMaker(min=min, max=max):
            ret = StringValidator(min, max)
        case _ListValidatorMaker(generic_argument=generic_argument, required=required, unique=unique):
            ret = ListValidator(annotation2validator(
                generic_argument, mode, default), required, unique)
        case Validator():
            ret = annotation
        case EnumType():
            if mode == 'json':
                ret = EnumValidator(annotation)
            else:
                ret = EnumStringValidator(annotation)
        case GenericAlias():
            ret = ListValidator(annotation2validator(
                *annotation.__args__, mode, default), False, True)
        case _LiteralGenericAlias():
            if mode == 'json':
                ret = LiteralValidator(annotation.__args__)
            else:
                ret = LiteralStringValidator(annotation.__args__)
        case _TypedDictMeta(__annotations__=annotations):
            ret = ObjectValidator({
                name: annotation2validator(ann, mode, _empty)
                for name, ann in annotations.items()
            })
        case _:
            ret = {
                bool: boolean if mode == 'json' else sbool,
                str: StringValidator(0, 0xffffffff),
                date: isodate,
                int: integer if mode == 'json' else sint,
                FileStorage: file
            }.get(annotation, dynamic)
    if default is _empty:
        return ret
    return DefaultValidator(ret, default)


class Api:
    def __init__(
        self,
        blueprint: Blueprint,
        name: str,
        url: Url,
        method: Literal['GET', 'POST'],
        doc: str,
        permission: Permission,
        params: dict[str, type],
        returns: type
    ) -> None:
        self.blueprint = blueprint
        self.name = name
        self.url = url
        self.method = method
        self.doc = doc
        self.permission = permission
        self.params = params
        self.returns = returns
        self.total_params = params | url.params

    apis: list['Api'] = []


def route(
    blueprint: Blueprint,
    url: Url,
    method: Literal['GET', 'POST'] = 'POST',
    *,
    mode: RouteMode
) -> Callable[[Callable], Callable]:
    from .util import render_template
    if mode == 'json':
        def error(errorn: int, kwargs=MappingProxyType({})) -> str:
            return json.dumps({'errorn': errorn, **kwargs})
    else:
        def error(msg: str, kwargs=MappingProxyType({})) -> str:
            return render_template(
                mode + '/error.html',
                msg=str(msg).format_map(kwargs)
            )

    def deco(fn: Callable) -> Callable:
        sig = signature(fn)
        form_params = ObjectValidator({
            name: annotation2validator(param.annotation, mode, param.default)
            for name, param in sig.parameters.items()
            if name not in url.params
        })

        @wraps(fn)
        def wrapper(*args, **kwargs):
            if mode == 'json':
                try:
                    args_dict = json.loads(request.get_data().decode())
                except (json.decoder.JSONDecodeError, UnicodeDecodeError):
                    args_dict = {}
            else:
                args_dict = request.form if method == 'POST' else request.args
            try:
                ret = fn(*args, **kwargs, **form_params.validate(args_dict))
                db.session.commit()
                if isinstance(ret, Response):
                    return ret
                if mode == 'json':
                    return json.dumps({
                        'errorn': ErrorCode.NO_ERROR,
                        'data': ret
                    })
                return ret
            except (NotFound, Forbidden):
                raise
            except ZvmsError as exn:
                db.session.rollback()
                return error(*exn.args)
            except Exception as exn:
                db.session.rollback()
                logger.exception(exn)
                abort(500)

        if mode == 'json':
            api = Api(
                blueprint,
                fn.__name__,
                url,
                method,
                fn.__doc__,
                getattr(fn, '__perm__', None),
                {
                    name: param.annotation
                    for name, param in sig.parameters.items()
                    if name not in url.params
                },
                sig.return_annotation
            )
            Api.apis.append(api)
            if not hasattr(blueprint, '__apis__'):
                blueprint.__apis__ = []
            blueprint.__apis__.append(api)
        blueprint.add_url_rule(
            url.string,
            view_func=wrapper,
            methods=[method]
        )
        return wrapper
    return deco


zvms_route = partial(route, mode='zvms')
toolkit_route = partial(route, mode='toolkit')
api_route = partial(route, mode='json')


def login_required(fn: Callable, json: bool = False) -> Callable:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'userid' not in session:
            if json:
                abort(403)
            return redirect('/user/login?redirect_to=' + quote(request.url))
        return fn(*args, **kwargs)
    return wrapper


api_login_required = partial(login_required, json=True)


def permission(perm: Permission) -> Callable[[Callable], Callable]:
    def deco(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if int(session.get('permission')) & (perm | Permission.ADMIN):
                return fn(*args, **kwargs)
            abort(403)
        wrapper.__perm__ = perm
        return wrapper
    return deco
