import re
import types
import inspect
from weakref import WeakSet
from importlib import import_module
from contextlib import contextmanager
from selenium.webdriver.common.action_chains import ActionChains as Action

from .errors import *
from .tools import *


__all__ = ["view", "container", "infinite_container",
    "mapping", "tree", "button", "menu"]


XPATH_IDENTIFIERS = ("//", "./", "..", "(/", "(.")


class view(structure):

    timeout = 15
    _instance = None
    highlight = "solid 1px red"
    selector = ("xpath", ".")

    def __init_subclass__(cls, **kwargs):
        if "selector" in cls.__dict__:
            method = ("xpath" if cls.selector[:2]
                in XPATH_IDENTIFIERS else "css")
            cls.selector = (method, cls.selector)
        if "imports" in kwargs:
            module = cls.__module__
            imports = kwargs["imports"]
            if not isinstance(imports, (list, tuple, set)):
                imports = [imports]
            for i in reversed(imports):
                views = import_views(i, module)
                for k, v in views.items():
                    setattr(cls, k, v)

    def __new__(cls, *args, **kwargs):
        self = new(view, cls, *args, **kwargs)
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

    def __init__(self, parent):
        parent._children.add(self)
        self.driver = parent.driver
        self._children = WeakSet()
        self.parent = parent
        self.refresh()

    def refresh(self):
        del self.instance
        for c in self._children:
            c.refresh()
        return self

    def __getattr__(self, name):
        i = self.instance
        try:
            return getattr(i, name)
        except Exception as e:
            raise AttributeError("%r has no attribute %r" % (self, name)) from e

    @property
    def text(self):
        text = self.instance.text
        if not text:
            text = self.get_attribute("textContent")
        return text

    @property
    def classes(self):
        c = self.attr("class")
        if c is None:
            return []
        else:
            return c.split()

    @singleton
    def instance(self):
        wait = Wait(self.timeout, self.parent)
        return wait.until(self._new_instance, "%r is still "
            "missing after %s seconds." % (self, self.timeout))

    @instance.callback
    def _on_instance(self):
        if self.highlight:
            try:
                script = "arguments[0].style.outline = %r" % self.highlight
                self.driver.execute_script(script, self.instance)
            except:
                pass

    def _new_instance(self, parent):
        self._instance = self._find_instance(parent)
        if self.exists():
            return self._instance
        else:
            self._instance = None

    def __del__(self):
        try:
            script = 'arguments[0].style.outline = null'
            self.driver.execute_script(script, self._instance)
        except:
            pass

    def _find_instance(self, parent):
        instance = parent.find_element(*self.selector)
        instance.location_once_scrolled_into_view
        return instance

    def exists(self):
        return True

    def action(self):
        return Action(self.driver).move_to_element(self.instance)

    def attr(self, name):
        return self.get_attribute(name)

    def css(self, name):
        return self.value_of_css_property(name)

    def prop(self, name):
        return self.get_property(name)

    def sleep(self, t):
        time.sleep(t)

    def __repr__(self):
        classname, selector = type(self).__name__, self.selector[1]
        return "%r.%s(%s)" % (self.parent, classname, selector)

    def __str__(self):
        return "%s.%s" % (self.parent, type(self).__name__)


class button(view):

    def exists(self):
        return self.is_displayed() and self.is_enabled()

    def click(self):
        # Chrome often shifts elements at the last moment. Thus references
        # to elements may have stale coordinates that need to be refreshed.
        Wait(self.timeout).until_is(self._clicked)

    def _clicked(self):
        try:
            self.instance.click()
        except:
            if isinstance(self.parent, view):
                self.parent.refresh()
            else:
                self.refresh()
            raise
        else:
            return True


class container(view):

    of = "item"

    class item(view):
        selector = "./*[%s]"
        timeout = 0.25

    @property
    def index(self):
        n = 1
        while True:
            yield n
            n += 1

    def __getitem__(self, index):
        item = getattr(self, self.of)
        if isinstance(item, view):
            raise TypeError("The selector %r of '%s' is not "
                "formatable" % (item.selector[1], item))
        return getattr(self, self.of)(index)

    def __iter__(self):
        self.instance
        for x in self.index:
            v = self._getitem(x)
            if v is not None:
                yield v
            else:
                break

    def _getitem(self, x):
        i = self[x]
        try:
            i.instance
        except Timeout:
            return None
        else:
            return i


class infinite_container(container):

    def __getitem__(self, index):
        if self._is_tail_index(index):
            return self._get_tail(index)
        items = iter(self)
        for x in self.items:
            try:
                i = next(items)
            except StopIteration:
                raise IndexError("Did not find %r in %s" % (index, self))
            else:
                if x == index:
                    return i

    def _get_tail(self, index):
        return tuple(self)[index]

    def _is_tail_index(self, index):
        try:
            return index < 0
        except:
            return False

    def __iter__(self):
        length = (-1, 0)
        while length[0] != length[1]:
            self.load()
            Wait(self.timeout).until_not(self.loading,
                "Still loading after %s seconds." % self.timeout)
            items = tuple(super().__iter__)
            last = items[-1].instance()
            self._scroll_into_view(last)
            yield from items[length[1]:]
            length[0], length[1] = length[1], len(items)

    def load(self):
        pass

    def loading(self):
        raise NotImplementedError()

    def _scroll_into_view(self, v):
        script = "arguments[0].scrollIntoView();"
        self.driver.execute_script(script, v)


class tree(container):

    def inverse(self):
        return zip(*self)

    class item(container):
        selector = "./*[%s]"

        item = this()
        timeout = 0.25

        def inverse(self):
            return zip(*self)


class mapping(container):

    minimum = None
    maximum = None

    def keys(self):
        return self.map.keys()

    def values(self):
        return self.map.values()

    def items(self):
        return self.map.items()

    def refresh(self):
        del self.map
        super().refresh()

    @singleton
    def map(self):
        return {x.key() : x for x in self._iter()}

    def __getitem__(self, key):
        return self.map[key]

    def __iter__(self):
        return iter(self.map)

    def _iter(self):
        self.instance
        for i, x in enumerate(self.index):
            if self.minimum is None or self.minimum < i:
                if self.maximum is None or self.maximum > i:
                    i = self._getitem(x)
                    try:
                        i.instance
                    except Timeout:
                        break
                    else:
                        yield i
                else:
                    break

    def _getitem(self, index):
        return getattr(self, self.of)(index)

    class item(container.item):

        def key(self):
            return self.text


class menu(button, mapping):

    _displayed = False
    always_displayed = False

    def open(self):
        if not self.always_displayed and not self._displayed:
            self.click()
            self._displayed = True

    def close(self):
        if not self.always_displayed and self._displayed:
            self.click()
            self._displayed = False

    @contextmanager
    def displayed(self):
        self.open()
        try:
            yield self
        finally:
            self.close()

    def select(self, value):
        e = self.find(value)
        e.click()
        return e

    def find(self, value):
        self.open()
        return self[value]

    class item(mapping.item):

        def click(self):
            p = self.parent
            if not p.always_displayed and p._displayed:
                p._enabled = False
            self.instance.click()


def import_views(package, origin=None):
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
        value = getattr(module, name)
        if inspect.isclass(value) and issubclass(value, view):
            if value.__module__ == module.__name__:
                views[name] = value
    return views
