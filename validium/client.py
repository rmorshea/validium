from selenium.webdriver import Remote
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities


def browser(browser, *args, **kwargs):
    capabilities = getattr(DesiredCapabilities, browser.upper())
    c = type(browser, (driver,), capabilities)
    return c(*args, **kwargs)


class driver:

    def __new__(self, *args, **kwargs):
        capabilities = {k : v for k, v in getmembers(self) if not k.startswith("_")}
        kwargs.update(desired_capabilities=capabilities)
        return Remote(*args, **kwargs)
