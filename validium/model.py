from weakref import WeakSet
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.wait import WebDriverWait as Wait

from . import base


class page:

    def __init_subclass__(cls, url):
        cls.url = url

    def __init__(self, driver):
        self.driver = driver
        self._active_children = WeakSet()

    @property
    def instance(self):
        return self.driver

    def refresh(self):
        self.driver.get(self.url)
        for c in self._active_children:
            c.refresh()
        return self

    def close(self):
        self.driver.close()


class view(base.view):

    timeout = 15

    _instance = None

    def refresh(self):
        self._instance = None
        for c in self._active_children:
            c.refresh()
        return self

    def exists(self, element):
        return True

    @property
    def instance(self):
        if self._instance is None:
            parent = self.parent.instance
            wait = Wait(parent, self.timeout)
            try:
                self._instance = wait.until(self._exists)
            except TimeoutException:
                raise TimeoutException("Failed to find %r "
                    "in %s seconds" % (self, self.timeout))
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


class views(base.views):

    minimum = 0
    timeout = 15

    def exists(self, element):
        return True


class node(base.node):
    vtype = view


class nodes(base.node):
    vtype = views
