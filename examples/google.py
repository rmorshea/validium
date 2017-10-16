from contextlib import closing
from selenium.webdriver import Chrome

from validium import *


exe = "/Users/RyanMorshead/Documents/Software/Development/imaginary-circle/misc/drivers/chromedriver"


class google(page, url="https://www.google.com/"):

    class search(view, xpath="//*[@id='lst-ib']"):

        hints = node(view, xpath='//*[@id="sbtc"]/div[2]/div[2]/div[1]/div/ul/li[%s]')
        button = node(view, xpath='//*[@id="sbtc"]/div[2]/div[2]/div[1]/div/ul/li[(last() - 1)]//input')

    class results(page, pattern="./search?"):

        timeout = 5

        class table(container, css="#center_col"):

            class item(mapping.item, xpath="(.//*[@class='g']//*[@class='rc'])[%s]"):

                link = node(button, xpath=".//a")
                cite = node(view, xpath=".//cite")
                description = node(view, xpath=".//span[@class='st']")


with closing(Chrome(exe)) as chrome:
    g = google(chrome)
    search = g.search
    search.send_keys("apple")
    search.button.click()

    r = g.results
    for result in r.table:
        result.link.click()
        r.get()


with closing(Chrome(exe)) as chrome:
    try:
        google(chrome).results
    except Exception as e:
        print(e)
