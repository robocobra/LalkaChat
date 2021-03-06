from distutils.core import setup
from main import VERSION

setup(
    name='LalkaChat',
    version=VERSION,
    packages=['', 'modules', 'modules.helpers', 'modules.messaging'],
    requires=['requests', 'cherrypy', 'ws4py', 'irc', 'wxpython', 'cefpython3', 'semantic_version', 'jinja2'],
    url='https://github.com/DeForce/LalkaChat',
    license='',
    author='CzT/DeForce',
    author_email='vlad@czt.lv',
    description=''
)
