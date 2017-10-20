import inspect
from functools import wraps
from importlib import import_module


def expectation(test):
    @wraps(test)
    def test_wrapper(*args, **kwargs):
        value = expected(test.__name__, test.__module__)
        return test(value, *args, **kwargs)
    return test_wrapper


def expected(name, module=None):
    if module is None:
        frame = inspect.currentframe()
        _global = frame.f_back.f_globals
        package, module = _global["__name__"]
    else:
        package, module = module.rsplit(".", 1)
    if module.startswith("test_"):
        module = module[5:]
    if name.startswith("test_"):
        name = name[5:]
    module = import_module(".".join([package, "expected", module]))
    try:
        return getattr(module, name)
    except AttributeError:
        raise ValueError("No expectation for %r was defined in %r." % (name, module))
