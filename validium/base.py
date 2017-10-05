import re
from weakref import WeakSet
from selenium.webdriver.support.wait import WebDriverWait as Wait


class methods:

    def __getattr__(self, name):
        try:
            return getattr(self.instance, name)
        except AttributeError:
            super(model, self).__getattr__(name)

    def attr(self, name):
        return self.instance.get_attribute(name)

    def prop(self, name):
        return self.instance.get_property(name)


class metaview(type):

    def __get__(vtype, obj, cls):
        if obj is not None:
            return vtype(obj)
        else:
            return vtype


class view(methods, metaclass=metaview):

    _stale = True

    def __init_subclass__(cls, **selector):
        if len(selector) > 1:
            raise ValueError("Pick one selector (e.g. xpath='//*')")
        cls.selector = None if not selector else next(iter(selector.items()))

    def __new__(cls, *args, **kwargs):
        self = _new_(view, cls, *args, **kwargs)
        return _init_(self, *args, **kwargs)

    def __init__(self, parent):
        parent._active_children.add(self)
        self._active_children = WeakSet()
        self.parent = parent
        self.refresh()

    def __repr__(self):
        full_selector = ("/".join(p.selector[1])
            for p in reversed(list(self.lineage))
            if isinstance(p, view))
        return "%s(%s)" % (self, full_selector)

    def __str__(self):
        lineage = reversed(tuple(self.lineage))
        return ".".join(type(v).__name__ for v in lineage)

    @property
    def lineage(self):
        v = self
        yield self
        while getattr(v, "parent", None) is not None:
            v = getattr(v, "parent", None)
            yield v


class metaviews(type):

    def __get__(vtype, obj, cls):
        if obj is not None:
            parent = obj.instance
            wait = Wait(parent, vtype.timeout)
            return wait.until(lambda p: vtype._find(obj, p))
        else:
            return vtype

    def _find(cls, parent, instance):
        elements = []
        for e in instance.find_elements(*cls.selector):
            new = cls(parent, e)
            exists = new.exists(e)
            if exists not in (True, False):
                raise TypeError("Exists method returned non-boolean value.")
            elif exists:
                elements.append(new)
        if len(elements) >= cls.minimum:
            return elements
        else:
            return False

class views(methods, metaclass=metaviews):

    def __init_subclass__(cls, **selector):
        if len(selector) > 1:
            raise ValueError("Pick one selector (e.g. xpath='//*')")
        cls.selector = None if not selector else next(iter(selector.items()))

    def __init__(self, parent, instance):
        self._active_children = WeakSet()
        self.parent = parent
        self.exists(instance)
        self._instance = instance

    @property
    def instance(self):
        return self._instance


class node:

    vtype = None

    def __init__(self, vtype=None, **selector):
        vtype = vtype or type(self).vtype
        if not issubclass(vtype, type(self).vtype):
            raise TypeError("Expected a subclass of %r, "
                "not %r" % (type(self).vtype, vtype))
        self.vtype = vtype
        self.selector = selector
        self.classdict = {}

    def __set_name__(self, cls, name):
        vtype = type(name, (self.vtype,), self.classdict, **self.selector)
        setattr(cls, name, vtype)

    def __call__(self, method):
        self.classdict["exists"] = staticmethod(method)
        return self


def _new_(origin, cls, *args, **kwargs):
    new = super(origin, cls).__new__
    if new is not object.__new__:
        return new(cls, *args, **kwargs)
    else:
        return new(cls)


def _init_(self, *args, **kwargs):
    if re.findall("%[\w]", self.selector[1]):
        def __format__(*positional, **keywords):
            if positional and keywords:
                raise ValueError("Expected position "
                    "or keyword arguments, not both.")
            inputs = positional or keywords
            method, selector = self.selector
            self.selector = (method, selector % inputs)
            self.__init__(*args, **kwargs)
            return self
        return __format__
    else:
        return self
