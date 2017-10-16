import time
import inspect
from functools import wraps
from .errors import *


_AttributeError = type("AttributeError", (Exception,), {})


class Wait:

    class DEFAULT: pass

    def __init__(self, timeout, *args, **kwargs):
        self.timeout, self.args, self.kwargs = timeout, args, kwargs

    def until_is(self, condition, reason=None, default=DEFAULT):
        return self.until(condition, reason, default, False)

    def until_is_not(self, condition, reason=None, default=DEFAULT):
        return self.until(condition, reason, default, True)

    def until(self, condition, reason=None, default=DEFAULT, inverse=False):
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
                    raise Timeout((reason or "%s seconds" % self.timeout) +
                        ("" if not len(errors) else " - %s" % errors[-1]))


def wait_until_is(timeout, reason=None, default=Wait.DEFAULT):
    def setup(method):
        @wraps(method)
        def wrapper(*args, **kwargs):
            return Wait(timeout, *args, **kwargs
                ).until_is(method, reason, default)
        return wrapper
    return setup


def wait_until_is_not(timout, reason=None, default=Wait.DEFAULT):
    def setup(method):
        @wraps(method)
        def wrapper(*args, **kwargs):
            return Wait(timeout, *args, **kwargs
                ).until_is_not(method, reason, default)
        return wrapper
    return setup



def wait(timeout, condition, reason=None, default=Wait.DEFAULT, inverse=False):
    return Wait(timeout).until(condition, reason, default, inverse)


class descriptor_type(type):

    def __get__(des, obj, cls):
        if obj is not None:
            return des(obj)
        else:
            return des


class structure(metaclass=descriptor_type):

    def __init_subclass__(cls, **kwargs):
        for name in dir(cls):
            value = getattr(cls, name)
            if inspect.isclass(value) and issubclass(value, structure):
                value.structural_parent = cls

    def __init__(self, parent):
        self.parent = parent

    def lineage(self, index=None):
        if index is not None:
            lineage = self._lineage()
            for i in range(index + 1):
                parent = next(lineage)
            return parent
        else:
            return tuple(self._lineage())

    def _lineage(self):
        parent = self
        while parent is not None:
            yield parent
            parent = getattr(parent, "parent", None)

    def __getattr__(self, name):
        try:
            return getattr(self.instance, name)
        except AttributeError:
            raise AttributeError("%s has no attribute %r" % (self, name))


class singleton:

    def __init__(self, factory):
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
            self._instance = None

        self._singleton = singleton

    def callback(self, callback):
        self._callback = callback

    def __set_name__(self, cls, name):
        setattr(cls, name, self._singleton)


def counter(n=0):
    while True:
        yield n
        n += 1


def new(origin, cls, args, kwargs):
    new = super(origin, cls).__new__
    if new is not object.__new__:
        return new(cls, *args, **kwargs)
    else:
        return new(cls)
