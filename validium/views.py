import re
import sys
import types
import inspect
from weakref import WeakSet
from importlib import import_module
from contextlib import contextmanager
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains as Action

from .errors import *
from .tools import *


__all__ = ["view", "container", "infinite_container",
    "mapping", "tree", "button", "menu", "field", "table"]


XPATH_IDENTIFIERS = ("//", "./", "..", "(/", "(.")


class view(structure):

    timeout = 20
    highlight = "solid 1px red"
    selector = ("xpath", ".")
    _persistant_instances = {}

    def __init_subclass__(cls, **kwargs):
        if "selector" in cls.__dict__:
            if not isinstance(cls.selector, tuple):
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

    @contextmanager
    def window_size(self, x, y):
        original = self.driver.get_window_size()
        self.driver.set_window_size(x, y)
        wait(5, lambda : (self.driver.get_window_size() == {"width": x, "height": y}),
            "failed to resize window to (%s, %s)" % (x, y))
        try:
            yield
        finally:
            self.driver.set_window_size(original["width"], original["height"])
            wait(5, lambda : (self.driver.get_window_size() == original),
            "failed to resize window to (%s, %s)" % (original["width"], original["height"]))

    @property
    def instance(self):
        inst = self._persistant_instances.get(self.selector)
        if inst is None:
            wait = Wait(self.timeout, self.parent)
            inst = wait.until(self._new_instance, "%r is still "
                "unavailable after %s seconds." % (self, self.timeout))
            self._persistant_instances[self.selector] = inst
            inst.location_once_scrolled_into_view
        return inst

    @instance.deleter
    def instance(self):
        if self.selector in self._persistant_instances:
            del self._persistant_instances[self.selector]

    def _new_instance(self, parent):
        inst = self._find_instance(parent)
        self._prep_instance(inst)
        self._persistant_instances[self.selector] = inst
        if self.exists():
            return inst
        else:
            del self._persistant_instances[self.selector]

    def _find_instance(self, parent):
        return parent.find_element(*self.selector)

    def _prep_instance(self, instance):
        if self.highlight:
            script = 'arguments[0].style.outline = %r' % self.highlight
            self.driver.execute_script(script, instance)
        original_execute = instance._execute
        def _execute(*args, **kwargs):
            try:
                return original_execute(*args, **kwargs)
            except StaleElementReferenceException:
                self.refresh().instance
                raw = self._persistant_instances[self.selector]
                return raw._execute(*args, **kwargs)
        instance._execute = _execute

    def __del__(self):
        inst = self._persistant_instances.get(self.selector)
        if inst is not None and sys.getrefcount(inst) == 1:
            try:
                inst = self._persistant_instances.pop(self.selector)
                script = 'arguments[0].style.outline = null'
                self.driver.execute_script(script, inst)
            except:
                pass


class field(view):

    @property
    def value(self):
        return self.prop("value")

    def send_special_keys(self, *keys):
        self.send_keys("".join(getattr(Keys, k.upper()) for k in keys))

    def backspace(self, n=1):
        self.send_special_keys(*(("backspace",)*n))

    def enter(self):
        self.send_special_keys("enter")


class button(view):

    click_timeout = 10

    def exists(self):
        return self.is_displayed() and self.is_enabled()

    def click(self):
        # Chrome often shifts elements at the last moment. Thus references
        # to elements may have stale coordinates that need to be refreshed.
        Wait(self.click_timeout).until_is(self._clicked, "failed to click %r" % self)

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
        timeout = 0.25
        selector = "./*[%s]"

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
        return {(x.key() if x.key else i) : x
            for i, x in enumerate(self._iter())}

    def __getitem__(self, key):
        return self.map[key]

    def __iter__(self):
        return iter(self.map)

    def _iter(self):
        self.instance
        for i, x in enumerate(self.index):
            if self.minimum is None or self.minimum < i:
                if self.maximum is None or self.maximum > i:
                    item = self._getitem(x)
                    try:
                        item.instance
                    except Timeout:
                        break
                    else:
                        yield item
                else:
                    break

    def _getitem(self, index):
        return getattr(self, self.of)(index)

    class item(container.item):

        def key(self):
            return self.text


class table(mapping):
    of = "row"

    class row(mapping, mapping.item):
        key = None
        selector = './tr[%s]'

        class item(mapping.item):
            selector = './td[%s]'


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

    class item(button, mapping.item):

        def click(self):
            p = self.parent
            if not p.always_displayed and p._displayed:
                p._enabled = False
            super().click()


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
