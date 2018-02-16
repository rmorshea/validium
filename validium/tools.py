import time
import inspect
from importlib import import_module
from weakref import ref
from functools import wraps
from .errors import *
from . import config


_AttributeError = type("AttributeError", (Exception,), {})


def import_structures(package, origin=None):
    if package.startswith("."):
        if origin is None:
            frame = inspect.currentframe()
            g = frame.f_back.f_globals
            package = g["__name__"] + package
        else:
            package = origin + package
    module = import_module(package)
    views = {}
    for name in dir(module):
        if not name.startswith("_"):
            value = getattr(module, name)
            if inspect.isclass(value) and issubclass(value, structure):
                if value.__module__ == module.__name__:
                    views[name] = value
    return views


class configurable:

    def __init__(self, name=None):
        if name is not None:
            self.default = getattr(config, name)

    def __set_name__(self, cls, name):
        if not hasattr(self, "default"):
            self.default = getattr(config, name)
        self.name = name

    def __get__(self, obj, cls):
        return (obj or cls).__dict__.setdefault(self.name, self.default)

    def __set__(self, obj, value):
        obj.__dict__[self.name] = value

    def __delete__(self, obj):
        obj.__dict__[self.name] = self.default


class Wait:

    class DEFAULT: pass

    def __init__(self, timeout, *args, **kwargs):
        self.timeout, self.args, self.kwargs = timeout, args, kwargs

    def until_is(self, condition, what, default=DEFAULT, period=0.2):
        return self.until(condition, what, default, False, period)

    def until_is_not(self, condition, what, default=DEFAULT, period=0.2):
        return self.until(condition, what, default, True, period)

    def until(self, condition, what, default=DEFAULT, inverse=False, period=0.2):
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
                    what = what(*self.args, **self.kwargs) if callable(what) else what
                    etype = type(what) if isinstance(what, Exception) else Timeout
                    p1 = "Doesn't expect" if inverse else "Expects"
                    p3 = "after %s seconds." % self.timeout
                    msg = " ".join([p1, what, p3])
                    if len(errors):
                        addon = " However one or more %s failures were encountered."
                        msg += addon % type(errors[-1]).__name__
                        raise etype(msg) from errors[-1]
                    else:
                        raise etype(msg)
            time.sleep(period)


def wait_until_is(timeout, what=None, default=Wait.DEFAULT, period=0.2):
    def setup(method):
        w = what or method.__doc__ or method.__name__.replace("_", " ")
        @wraps(method)
        def wrapper(*args, **kwargs):
            return Wait(timeout, *args, **kwargs
                ).until_is(method, w, default, period)
        return wrapper
    return setup


def wait_until_is_not(timout, what=None, default=Wait.DEFAULT, period=0.2):
    def setup(method):
        w = what or method.__doc__ or method.__name__.split()
        @wraps(method)
        def wrapper(*args, **kwargs):
            return Wait(timeout, *args, **kwargs
                ).until_is_not(method, w, default, period)
        return wrapper
    return setup



def wait(timeout, condition, what, default=Wait.DEFAULT, inverse=False, period=0.2):
    return Wait(timeout).until(condition, what, default, inverse, period)


class meta_structure(type):

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


class structure(metaclass=meta_structure):

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


def javascript(functions, script):
    functions = functions.replace(" ", "").split(",")
    context = "\n".join(_javascript[f] for f in functions)
    return context + "\n" + script


_javascript = {
    "fireEvent": """
      function fireEvent(el, etype){
        if (el.fireEvent) {
          el.fireEvent('on' + etype);
        } else {
          var evObj = document.createEvent('Events');
          evObj.initEvent(etype, true, false);
          el.dispatchEvent(evObj);
        }
      }
      """
}

def chains(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        method(self, *args, **kwargs)
        return self
    return wrapper
