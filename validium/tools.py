import time
import inspect
from weakref import ref
from functools import wraps
from .errors import *


_AttributeError = type("AttributeError", (Exception,), {})


class Wait:

    class DEFAULT: pass

    def __init__(self, timeout, *args, **kwargs):
        self.timeout, self.args, self.kwargs = timeout, args, kwargs

    def until_is(self, condition, reason=None, default=DEFAULT, period=0.2):
        return self.until(condition, reason, default, False, period)

    def until_is_not(self, condition, reason=None, default=DEFAULT, period=0.2):
        return self.until(condition, reason, default, True, period)

    def until(self, condition, reason=None, default=DEFAULT, inverse=False, period=0.2):
        errors = []
        stop = time.time() + self.timeout
        while True:
            try:
                result = condition(*self.args, **self.kwargs)
            except Exception as e:
                errors.append(e)
            else:
                if bool(result) is (not inverse):
                    return result
            if time.time() > stop:
                if default is not Wait.DEFAULT:
                    return default
                else:
                    reason = reason or getattr(condition, "__doc__", None)
                    too_long = Timeout(reason or "%s seconds" % self.timeout)
                    if len(errors):
                        raise too_long from errors[-1]
                    else:
                        raise too_long
            time.sleep(period)


def wait_until_is(timeout, reason=None, default=Wait.DEFAULT, period=0.2):
    def setup(method):
        @wraps(method)
        def wrapper(*args, **kwargs):
            return Wait(timeout, *args, **kwargs
                ).until_is(method, reason, default, period)
        return wrapper
    return setup


def wait_until_is_not(timout, reason=None, default=Wait.DEFAULT, period=0.2):
    def setup(method):
        @wraps(method)
        def wrapper(*args, **kwargs):
            return Wait(timeout, *args, **kwargs
                ).until_is_not(method, reason, default, period)
        return wrapper
    return setup



def wait(timeout, condition, reason=None, default=Wait.DEFAULT, inverse=False, period=0.2):
    return Wait(timeout).until(condition, reason, default, inverse, period)


class metastructure(type):

    def __get__(des, obj, cls):
        if obj is not None:
            return des(obj)
        else:
            return des


class this:

    def __get__(self, obj, cls):
        if hasattr(cls, "__get__"):
            return cls.__get__(obj, cls)
        else:
            return cls


class structure(metaclass=metastructure):

    def __init__(self, parent):
        self.parent = parent

    def lineage(self, index=None, name=None):
        if index is not None:
            if index > 0:
                lineage = self._lineage()
                for i in range(index + 1):
                    parent = next(lineage)
                return parent
            else:
                return tuple(self._lineage())[index]
        elif name is not None:
            for p in self._lineage():
                if type(p).__name__ == name:
                    return p
            else:
                raise ValueError("No parent with the "
                    "type name %r exists" % name)
        else:
            return tuple(self._lineage())

    def _lineage(self):
        parent = self
        while parent is not None:
            yield parent
            parent = getattr(parent, "parent", None)


class singleton:

    def __init__(self, factory):
        self._callback = None
        attr = "_%s" % factory.__name__
        lock = "_%s_lock" % factory.__name__

        @property
        @wraps(factory)
        def singleton(obj):
            try:
                if getattr(obj, attr, None) is None:
                    setattr(obj, attr, factory(obj))
                if lock not in obj.__dict__:
                    setattr(obj, lock, False)
                locked = getattr(obj, lock)
                if not locked and self._callback:
                    setattr(obj, lock, True)
                    self._callback(obj)
                    setattr(obj, lock, False)
                return getattr(obj, attr)
            except AttributeError as e:
                raise _AttributeError(e) from e

        @singleton.deleter
        def singleton(self):
            setattr(self, attr, None)

        self._singleton = singleton

    def callback(self, callback):
        self._callback = callback

    def __set_name__(self, cls, name):
        setattr(cls, name, self._singleton)


def counter(n=0):
    while True:
        yield n
        n += 1


def new(origin, cls, *args, **kwargs):
    _new = super(origin, cls).__new__
    if _new is not object.__new__:
        return _new(cls, *args, **kwargs)
    else:
        return _new(cls)
