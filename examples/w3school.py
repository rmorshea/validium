from contextlib import closing
from selenium.webdriver import Chrome

from validium import *


exe = "/Users/RyanMorshead/Documents/Software/Development/imaginary-circle/misc/drivers/chromedriver"


class w3schools(page):
    url = "https://www.w3schools.com/"

    class sidebar(menu):
        selector = "//*[contains(@class, 'w3-sidebar')]"

        always_displayed = True

        class item(menu.item):
            highlight = False
            selector = ".//a[%s]"

            def key(self):
                return self.text.lower()


class tables_tutorial(w3schools):
    url = "./html/html_tables.asp"

    class customers(tree):
        selector = "//*[@id='customers']/tbody"


with closing(Chrome(exe)) as chrome:
    home = w3schools(chrome)

    home.sidebar.select("learn html")
    home.sidebar.select("html tables")

    tutorial = tables_tutorial(home)

    for c in tutorial.customers.inverse():
        t = c[0].text
        divider = "-" * len(t)
        print(divider)
        print(t)
        print(divider)
        for i in c[1:]:
            print(i.text)
