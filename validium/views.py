import re
import sys
import types
import inspect
import logging
from weakref import WeakSet
from logging import getLogger
from contextlib import contextmanager
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains as Action

from . import config
from .errors import *
from .tools import *
from .pages import page


__all__ = ["slowdown", "view", "container", "infinite_container",
    "mapping", "tree", "button", "menu", "field", "table"]


XPATH_IDENTIFIERS = ("//", "./", "..", "(/", "(.")


@contextmanager
def slowdown(t):
    hold = config.slowdown
    config.slowdown = t
    try:
        yield
    finally:
        config.slowdown = hold


def call_string(args, kwargs, form=(lambda i : "%s=%r" % i)):
    a, kw = map(str, args), map(form, kwargs.items())
    return ", ".join(tuple(a) + tuple(kw))


class view(structure):

    _structure_source = "selector"
    highlight = "solid 1px red"
    selector = ("xpath", ".")
    _persistant_instances = {}
    timeout = configurable()
    slowdown = configurable()

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
                views = import_structures(i, module)
                for k, v in views.items():
                    setattr(cls, k, v)

    def __new__(cls, *args, **kwargs):
        self = new(view, cls, *args, **kwargs)
        if re.findall(r"[^{]{", self.selector[1]):
            def __format__(*a, **kw):
                method, selector = self.selector
                self.selector = (method, selector.format(*a, **kw))
                self.__init__(*args, **kwargs)
                return self
            return __format__
        else:
            return self

    def __init__(self, parent):
        if hasattr(parent, "transition_to"):
            parent.transition_to(self)
        if not isinstance(parent, view) and self.selector == ("xpath", "."):
            self.selector = ("xpath", "//*")
        if isinstance(parent, page):
            self.page = parent
        else:
            self.page = getattr(parent, "page", None)
        parent._children.add(self)
        self.driver = parent.driver
        self._children = WeakSet()
        self.parent = parent
        self.refresh()
        self.transition_from(parent)

    def transition_to(self, child):
        pass

    def transition_from(self, parent):
        pass

    @chains
    def refresh(self):
        p = self.page
        if p is not None:
            p._get(redirection=False)
        del self.instance
        for c in self._children:
            c.refresh()

    @chains
    def sleep(self, t):
        time.sleep(t)

    @chains
    def scroll_to(self):
        self.instance.location_once_scrolled_into_view

    @property
    def text(self):
        return self.instance.text

    @property
    def plain_text(self):
        clean = self.text.replace("\n", " ").replace("\t", " ")
        return " ".join(t for t in clean.split(" ") if t)

    @property
    def classes(self):
        c = self.attr("class")
        if c is None:
            return []
        else:
            return c.split()

    def exists(self):
        try:
            self.instance
        except:
            return False
        else:
            return True

    def action(self):
        return Action(self.driver).move_to_element(self.instance)

    def attr(self, name):
        return self.get_attribute(name)

    def css(self, name):
        return self.value_of_css_property(name)

    def prop(self, name):
        return self.get_property(name)

    def event(self, etype):
        script = "fireEvent(arguments[0], %r)" % etype
        return self._js("fireEvent", script, self.instance)

    @contextmanager
    def window_size(self, x, y):
        original = self.driver.get_window_size()
        self.driver.set_window_size(x, y)
        wait(5, lambda : (self.driver.get_window_size() == {"width": x, "height": y}),
            "to resize window (%s, %s)" % (x, y))
        try:
            yield
        finally:
            self.driver.set_window_size(original["width"], original["height"])
            wait(5, lambda : (self.driver.get_window_size() == original),
            "to resized window (%s, %s)" % (original["width"], original["height"]))

    def __getattr__(self, name):
        i = self.instance
        try:
            return getattr(i, name)
        except Exception as e:
            raise AttributeError("%r has no attribute %r" % (self, name))

    def __repr__(self):
        classname, selector = type(self).__name__, self.selector[1]
        return "%r.%s(%s)" % (self.parent, classname, selector)

    def __str__(self):
        return "%s.%s" % (self.parent, type(self).__name__)

    def _js(self, functions, script, *args):
        script = javascript(functions, script)
        return self.driver.execute_script(script, *args)

    @property
    def instance(self):
        inst = self._persistant_instances.get(self.selector)
        if inst is None:
            logger = getLogger(self.__module__)
            logger.debug("New instance of %s" % self)
            wait = Wait(self.timeout, self.parent)
            inst = wait.until(self._new_instance, "%r to be available" % self)
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
        instance._scroll_into_view_lock = False
        def _execute(*args, **kwargs):
            cs = call_string(args, kwargs)
            logging.debug("%s(%s)" % (self, cs))
            time.sleep(config.slowdown)
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

    def send_keys(self, *keys, specials=True):
        if specials:
            _keys = []
            for k in keys:
                if k.startswith(":") and not k.startswith("::"):
                    if k.endswith(":") and not k.endswith("::"):
                        k = getattr(Keys, k[1:-1].upper())
                _keys.append(k)
            keys = _keys
        text = "".join(keys)
        return self.instance.send_keys(text)

    def send_special_keys(self, *keys):
        self.send_keys("".join(getattr(Keys, k.upper()) for k in keys))

    def backspace(self, n=1):
        self.send_special_keys(*(("backspace",)*n))

    def enter(self):
        self.send_special_keys("enter")


class button(view):

    def exists(self):
        return self.is_displayed() and self.is_enabled()


class container(view):

    holding = "item"

    class item(view):
        timeout = configurable("item_timeout")
        selector = "./*[{}]"

    @property
    def index(self):
        n = 1
        while True:
            yield n
            n += 1

    def refresh(self):
        del self._list
        super().refresh()

    @singleton
    def _list(self):
        return list(self._iter())

    def __getitem__(self, index):
        return self._list[index]

    def __iter__(self):
        return iter(self._list)

    def _iter(self):
        self.instance
        for x in self.index:
            v = self._getitem(x)
            if v is not None:
                yield v
            else:
                break

    def _getitem(self, x):
        instance = getattr(self, self.holding)
        if isinstance(instance, view):
            raise TypeError("The selector %r of '%s' is not "
                "formatable" % (instance.selector[1], instance))
        item = instance(x)
        try:
            item.instance
        except Timeout:
            return None
        else:
            return item


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
            Wait(self.timeout).until_not(self.loading, "loading")
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
        selector = "./*[{}]"
        timeout = configurable("item_timeout")
        item = this()

        def inverse(self):
            return zip(*self)


class mapping(container):

    minimum = None
    maximum = None

    def keys(self):
        return self._map.keys()

    def values(self):
        return self._map.values()

    def items(self):
        return self._map.items()

    def refresh(self):
        del self._map
        super().refresh()

    @singleton
    def _map(self):
        return {(x.key() if x.key else i) : x
            for i, x in enumerate(self._iter())}

    def __getitem__(self, key):
        return self._map[key]

    def __iter__(self):
        return iter(self._map)

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
        return getattr(self, self.holding)(index)

    class item(container.item):

        def key(self):
            return self.plain_text


class table(mapping):
    of = "row"

    class row(mapping, mapping.item):
        key = None
        selector = './tr[{}]'

        class item(mapping.item):
            selector = './td[{}]'


class menu(button, mapping):

    _displayed = False
    always_displayed = False
    initially_displayed = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._displayed = cls.initially_displayed

    @chains
    def open(self):
        if not self.always_displayed and not self._displayed:
            self.click()
            self._displayed = True

    @chains
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
            self.instance.click()
