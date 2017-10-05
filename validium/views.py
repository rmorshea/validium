import re
from weakref import WeakSet
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.wait import WebDriverWait as Wait


class ViewError(Exception):
    pass


class Timeout(ViewError):
    pass


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

    @property
    def find_element(self):
        return self.driver.find_element

    @property
    def find_elements(self):
        return self.driver.find_elements

    def __repr__(self):
        return type(self).__name__


class descriptor_type(type):

    def __get__(des, obj, cls):
        if obj is not None:
            return des(obj)
        else:
            return des


class view(metaclass=descriptor_type):

    timeout = 15

    def __new__(cls, *args, **kwargs):
        self = _new_(view, cls, *args, **kwargs)
        return _init_(self, *args, **kwargs)

    def __init_subclass__(cls, **selector):
        if len(selector) > 1:
            raise ValueError("Pick one selector (e.g. xpath='//*')")
        if selector:
            cls.selector = next(iter(selector.items()))

    def __init__(self, parent):
        if isinstance(parent, view):
            parent._children.add(self)
        self._children = WeakSet()
        self.parent = parent
        self.refresh()

    def refresh(self):
        self._instance = None
        for c in self._children:
            c.refresh()

    def instance(self):
        if self._instance is None:
            wait = Wait(self.parent, self.timeout)
            try:
                self._instance = wait.until(self._new)
            except TimeoutException:
                raise Timeout("%s is still missing after "
                    "%s seconds." % (self, self.timeout))
        return self._instance

    def find(self, parent):
        return parent.find_element(*self.selector)

    def exists(self, element):
        return True

    def __getattr__(self, name):
        try:
            return getattr(self.instance(), name)
        except AttributeError:
            super(model, self).__getattr__(name)

    def attr(self, name):
        return self.get_attribute(name)

    def prop(self, name):
        return self.get_property(name)

    def _new(self, parent):
        instance = self.find(parent)
        if self.exists(instance):
            return instance

    def __repr__(self):
        classname, selector = type(self).__name__, self.selector[1]
        return "%r.%s(%s)" % (self.parent, classname, selector)

    def __str__(self):
        return "%s.%s" % (self.parent, type(self).__name__)


class node:

    def __init__(self, of=view, **selector):
        self._of = of
        self.selector = selector
        self.classdict = {}

    def of(self, name):
        return type(name, (self._of,), self.classdict, **self.selector)

    def __set_name__(self, cls, name):
        setattr(cls, name, self.of(name))

    def __call__(self, method):
        self.classdict["exists"] = staticmethod(method)
        return self


class collection:

    def __init__(self, contains=None, **attrs):
        if isinstance(contains, node):
            contains = contains.of(self.name)
        self.contains = contains
        self.attrs = attrs

    def __call__(self, contains):
        if isinstance(contains, node):
            contains = contains.of(self.name)
        self.contains = contains
        return self

    def __set_name__(self, cls, name):
        self.name = name

    def __get__(self, obj, cls):
        if obj is not None:
            index = 0
            found = []
            while True:
                new = self.contains(obj)(index + 1)
                for k, v in self.attrs.items():
                    setattr(new, k, v)
                try:
                    new.instance()
                except Timeout:
                    break
                else:
                    found.append(new)
                index += 1
            return found
        else:
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
