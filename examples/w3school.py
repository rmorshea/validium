from contextlib import closing
from selenium.webdriver import Chrome

from validium import *


exe = "/Users/RyanMorshead/Documents/Software/Development/imaginary-circle/misc/drivers/chromedriver"


class w3schools(page, url="https://www.w3schools.com/"):

    class sidebar(menu, xpath="//*[contains(@class, 'w3-sidebar')]"):

        class item(menu.item, xpath=".//a[%s]"):

            def matches(self, text):
                return self.text.lower().endswith(text.lower())


class tables_tutorial(w3schools, url="./html/html_tables.asp"):

    class customers(tree, xpath="//*[@id='customers']/tbody"): pass


with closing(Chrome(exe)) as chrome:
    home = w3schools(chrome)

    home.sidebar.select("html")
    home.sidebar.select("tables")

    tutorial = tables_tutorial(home)

    for c in tutorial.customers.inverse():
        t = c[0].text
        divider = "-" * len(t)
        print(divider)
        print(t)
        print(divider)
        for i in c[1:]:
            print(i.text)

    tutorial.sidebar.select("home")
