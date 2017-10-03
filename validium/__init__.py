import time
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
        self.refresh()

    def refresh(self):
        self.driver.get(self.url)

    def instance(self):
        return self.driver

    def close(self):
        self.driver.close()


class metaview(type):

    def __get__(vtype, obj, cls):
        if obj is not None:
            return vtype(obj)
        else:
            return vtype


class view(metaclass=metaview):

    timeout = 30

    def __init_subclass__(cls, **selector):
        if len(selector) != 1:
            raise ValueError("Pick one selector (e.g. xpath='//*')")
        cls.selector = next(iter(selector.items()))

    def __init__(self, parent):
        self.parent = parent

    def __getattr__(self, name):
        return getattr(self.instance(), name)

    def child(self, selector):
        return self.find_element(self.selector[0], selector)

    def instance(self):
        return Wait(self.parent.instance(), self.timeout).until(self.exists)

    def exists(self, driver):
        return driver.find_element(*self.selector)

    def __repr__(self):
        lineage = reversed(tuple(self.lineage))
        path = ".".join(type(v).__name__ for v in lineage)
        return "%s(%s)" % (path, self.selector[1])

    @property
    def lineage(self):
        v = self
        yield self
        while getattr(v, "parent", None) is not None:
            v = getattr(v, "parent", None)
            yield v


class node:

    exists = None

    def __init__(self, vtype=view, **selector):
        self.vtype = vtype
        self.selector = selector

    def __set_name__(self, cls, name):
        classdict = {"exists": self.exists} if self.exists else {}
        v = type(name, (self.vtype,), classdict, **self.selector)
        setattr(cls, name, v)

    def __call__(self, method):
        @wraps(method)
        def exists(self, driver):
            element = driver.find_element(*self.selector)
            result = method(element)
            if result is True:
                return element
            else:
                return result
        self.exists = exists
        return self
