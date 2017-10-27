from .views import *
from .client import browser, driver
from .pages import page, redirect
from .tools import Wait, wait, wait_until_is, wait_until_is_not


class node:

    def __init__(self, vtype, **classdict):
        self.vtype, self.classdict = vtype, classdict

    def __set_name__(self, cls, name):
        setattr(cls, name, type(name, (self.vtype,), self.classdict))


__all__ = ["node", "slowdown", "view", "container", "infinite_container",
    "mapping", "tree", "button", "menu", "field", "table",
    "browser", "driver", "page", "redirect", "Wait", "wait",
    "wait_until_is", "wait_until_is_not"]
