import re
import time
from weakref import WeakSet
from contextlib import contextmanager
from selenium.webdriver import Remote


from .errors import *
from .tools import *


class page(structure):

    url = None
    pattern = None
    timeout = 15
    redirect = None
    _structure_source = "url"

    def __init_subclass__(cls, **kwargs):
        if "imports" in kwargs:
            module = cls.__module__
            imports = kwargs["imports"]
            if not isinstance(imports, (list, tuple, set)):
                imports = [imports]
            for i in reversed(imports):
                views = import_structures(i, module)
                for k, v in views.items():
                    setattr(cls, k, v)

    def __new__(cls, *args, **kwargs):
        self = new(page, cls, *args, **kwargs)
        if self.url is not None and re.findall("[^{]{", self.url):
            def __format__(*a, **kw):
                self.url = self.url.format(*a, **kw)
                self.__init__(*args, **kwargs)
                return self
            return __format__
        else:
            return self

    def __init__(self, parent):
        if not isinstance(parent, (Remote, page)):
            raise TypeError("The parent of a page "
                "must be a webdriver of another page")
        else:
            self._children = WeakSet()
            if isinstance(parent, Remote):
                self.driver = parent
            else:
                self.driver = parent.driver
            self.parent = parent
        self._transition()

    def __getattr__(self, name):
        i = self.instance
        try:
            return getattr(i, name)
        except Exception as e:
            raise AttributeError("%r has no attribute %r" % (self, name)) from e

    def _transition(self):
        contingent = not self.url or self.url.startswith("./")
        if contingent and not isinstance(self.parent, page):
            raise TypeError("The parent of a page with a contingent url "
                "must be another page object, not %r." % self.parent)
        if not self.url:
            if self.pattern.startswith("./"):
                self.pattern = self.parent.url + self.pattern[2:]
            elif self.pattern.startswith("\.\/"):
                self.pattern = "./" + self.pattern[4:]
            wait(self.timeout,
                 lambda : (
                    re.match(self.pattern, self.current_url) and self.is_loaded()),
                "to transition from %r to a url matching %r" %
                (self.current_url, self.pattern))
            self.url = self.current_url
        else:
            if self.url.startswith("./"):
                self.url = self.parent.url + self.url[2:]
            initial = self.driver.current_url
            if initial != self.url:
                self.driver.get(self.url)
                for name in dir(type(self)):
                    value = getattr(type(self), name)
                    if inspect.isclass(value) and issubclass(value, redirect):
                        getattr(self, name).callback()
                        break
                wait(self.timeout, lambda : (
                        self.url == self.current_url and self.is_loaded()),
                    "to transition from %r to %r" % (self.current_url, self.url))

    @contextmanager
    def window_size(self, x, y):
        original = self.driver.get_window_size()
        self.driver.set_window_size(x, y)
        wait(3, lambda : (
            self.driver.get_window_size()
            == {"width": x, "height": y}))
        try:
            yield
        finally:
            self.driver.set_window_size(original["width"], original["height"])
            wait(3, lambda : (self.driver.get_window_size() == original))

    def is_loaded(self):
        return True

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, value):
        self.driver.set_window_size(*value)

    @property
    def instance(self):
        # self._transition()
        return self.parent

    def get(self, url=None, force=False):
        if url is not None:
            self.driver.get(url)
        elif force or self.current_url != self.url:
            self._transition()
        for c in self._children:
            c.refresh()
        return self

    def refresh(self):
        self.get(self.current_url)
        for c in self._active_children:
            c.refresh()
        return self

    def close(self):
        self.driver.close()

    def sleep(self, t):
        time.sleep(t)

    def __repr__(self):
        return type(self).__name__


class redirect(page):

    def callback(self):
        raise NotImplementedError()
