from contextlib import closing
from selenium.webdriver import Chrome

from validium import *

import os
exe = os.path.expanduser("~/Downloads/chromedriver")


class google(page):
    url = "https://www.google.com/"

    class search(view):
        selector = "//*[@id='lst-ib']"

        class hints(view):
            selector = '//*[@id="sbtc"]/div[2]/div[2]/div[1]/div/ul/li[%s]'
        class go(button):
            selector = '//*[@id="sbtc"]/div[2]/div[2]/div[1]/div/ul/li[(last() - 1)]//input'

    class results(page):

        pattern="./search?"

        timeout = 5

        class table(container):

            selector = "#center_col"

            class item(mapping.item):

                selector = "(.//*[@class='g']//*[@class='rc'])[%s]"

                class link(button):
                    selector = ".//a"
                class cite(view):
                    selector = ".//cite"
                class description(view):
                    selector = ".//span[@class='st']"


with closing(Chrome(exe)) as chrome:
    g = google(chrome)
    search = g.search
    search.send_keys("apple")
    search.go.click()

    r = g.results
    for result in r.table:
        result.link.click()
        r.get()


with closing(Chrome(exe)) as chrome:
    try:
        google(chrome).results
    except Exception as e:
        print(e)
