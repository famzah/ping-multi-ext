# Always prefer setuptools over distutils
from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / 'README.rst').read_text(encoding='utf-8')

import ping_multi_ext # version

setup(
    name='ping-multi-ext',
    version=ping_multi_ext.version,

    description='Interactively ping one or many hosts from one or multiple locations (locally or via SSH)',
    long_description=long_description,
    long_description_content_type='text/x-rst',
    url='https://github.com/famzah/ping-multi-ext',

    author='Ivan Zahariev (famzah)',
    #author_email='author@example.com',  # Optional

    # list of valid classifiers, see https://pypi.org/classifiers/
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Topic :: Internet',
        'Topic :: System :: Networking :: Monitoring',
        'Topic :: Terminals',
        'Topic :: Utilities',
    ],

    keywords='ping, multi, console, ssh, terminal, interactive',

    # When your source code is in a subdirectory under the project root, e.g.
    # `src/`, it is necessary to specify the `package_dir` argument.
    #package_dir={'': 'src'},  # Optional

    # You can just specify package directories manually here if your project is
    # simple. Or you can use find_packages().
    #
    # Alternatively, if you just want to distribute a single Python file, use
    # the `py_modules` argument instead as follows, which will expect a file
    # called `my_module.py` to exist:
    #
    #   py_modules=["my_module"],
    #
    #packages=find_packages(where='src'),  # Required
    packages=['ping_multi_ext'],

    python_requires='>=3.6, <4',
    install_requires=['blessings', 'curtsies'],

    # List additional groups of dependencies here (e.g. development
    # dependencies). Users will be able to install these using the "extras"
    # syntax, for example:
    #
    #   $ pip install sampleproject[dev]
    #
    # Similar to `install_requires` above, these must be valid existing
    # projects.
    extras_require={
    },

    # If there are data files included in your packages that need to be
    # installed, specify them here.
    package_data={
    },

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/distutils/setupscript.html#installing-additional-files
    #
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    data_files=[],

    entry_points={
        'console_scripts': [
            'ping-raw-multi=ping_multi_ext.cmd_raw:main',
            'ping-multi=ping_multi_ext.cmd_multi:main',
        ],
    },

    project_urls={
        'Bug Reports': 'https://github.com/famzah/ping-multi-ext/issues',
        'Source': 'https://github.com/famzah/ping-multi-ext',
    },
)
