import re
from sys import getrefcount
from weakref import WeakSet
from functools import wraps
from contextlib import closing
from inspect import isclass, getmembers

from selenium.webdriver import Remote
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.wait import WebDriverWait as Wait


def browser(browser, *args, **kwargs):
    capabilities = getattr(DesiredCapabilities, browser.upper())
    c = type(browser, (driver,), capabilities)
    return c(*args, **kwargs)


class driver:

    def __new__(self, *args, **kwargs):
        capabilities = {k : v for k, v in getmembers(self) if not k.startswith("_")}
        kwargs.update(desired_capabilities=capabilities)
        return Remote(*args, **kwargs)


class page:

    def __init_subclass__(cls, url):
        cls.url = url

    def __init__(self, driver, *args, **kwargs):
        self.driver = driver(*args, **kwargs)
        self._active_instances = WeakSet()
        self.refresh()

    @property
    def instance(self):
        return self.driver

    def refresh(self):
        self.driver.get(self.url)
        for i in self._active_instances:
            i.refresh()

    def close(self):
        self.driver.close()


class metaview(type):

    def __get__(vtype, obj, cls):
        if obj is not None:
            return vtype(obj)
        else:
            return vtype


class view(metaclass=metaview):

    timeout = 10
    _stale = True

    def __init_subclass__(cls, **selector):
        if len(selector) > 1:
            raise ValueError("Pick one selector (e.g. xpath='//*')")
        cls.selector = None if not selector else next(iter(selector.items()))

    def __new__(cls, *args, **kwargs):
        self = _new_(view, cls, *args, **kwargs)
        return _init_(self, *args, **kwargs)

    def __init__(self, parent):
        parent._active_instances.add(self)
        self._active_instances = WeakSet()
        self.parent = parent
        self.refresh()

    def refresh(self):
        self._instance = None
        for i in self._active_instances:
            i.refresh()

    def __getattr__(self, name):
        try:
            return getattr(self.instance, name)
        except AttributeError:
            return super(view, self).__getattr__(name)

    @property
    def instance(self, new=False):
        if self._instance is None:
            parent = self.parent.instance
            wait = Wait(parent, self.timeout)
            try:
                self._instance = wait.until(self._exists)
            except TimeoutException:
                raise TimeoutException("Failed to find %r in %s seconds" %
                    ("/".join(p.selector[1] for p in
                    reversed(list(self.lineage))
                    if isinstance(p, view)),
                    self.timeout))
        return self._instance

    def _exists(self, parent):
        element = self._find(parent)
        result = self.exists(element)
        if result not in (True, False):
            raise TypeError("Exists method returned non-boolean value.")
        elif result is True:
            return element
        else:
            return result

    def _find(self, parent):
        return parent.find_element(*self.selector)

    def exists(self, element):
        return True

    def __repr__(self):
        return "%s(%s)" % (self, self.selector[1])

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


class views(view):

    def __iter__(self):
        return iter(self.instance)

    def __getitem__(self, index):
        return self.instance[index]

    def _find(self, parent):
        return parent.find_elements(*self.selector)


class node:

    def __init__(self, vtype=view, **selector):
        self.vtype = vtype
        self.selector = selector
        self.classdict = {}

    def __set_name__(self, cls, name):
        vtype = type(name, (self.vtype,), self.classdict, **self.selector)
        setattr(cls, name, vtype)

    def __call__(self, method):
        self.classdict["exists"] = staticmethod(method)
        return self


class nodes(node):

    def __init__(self, vtype=views, **selector):
        super(nodes, self).__init__(vtype, **selector)


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


def _new_(origin, cls, *args, **kwargs):
    new = super(origin, cls).__new__
    if new is not object.__new__:
        return new(cls, *args, **kwargs)
    else:
        return new(cls)
