# PyMySQL is a pure-Python MySQL driver, so no C compiler is needed on Windows.
# It registers itself as "MySQLdb", which is the module Django's MySQL backend imports.
import pymysql

pymysql.install_as_MySQLdb()
