import re
import time
from weakref import WeakSet
from selenium.webdriver import Remote


from .errors import *
from .tools import *


class page(structure):

    url = None
    patter = None
    timeout = 15

    def __new__(cls, *args, **kwargs):
        self = new(page, cls, *args, **kwargs)
        if self.url is not None and re.findall("%[\w]", self.url):
            def __format__(*positional, **keywords):
                if positional and keywords:
                    raise ValueError("Expected position "
                        "or keyword arguments, not both.")
                self.url = self.url % (positional or keywords)
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
                 lambda : re.match(self.pattern, self.current_url),
                "Failed to transition from %r to a url matching %r after "
                "%s seconds" % (self.current_url, self.pattern, self.timeout))
            self.url = self.current_url
        else:
            if self.url.startswith("./"):
                self.url = self.parent.url + self.url[2:]
            initial = self.driver.current_url
            if initial != self.url:
                self.get(self.url)
                wait(self.timeout, lambda : self.url == self.current_url,
                    ("Failed to transition from %r to %r after %s "
                    "seconds" % (self.current_url, self.url, self.timeout)))

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
