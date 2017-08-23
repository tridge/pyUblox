from __future__ import absolute_import, print_function

import setuptools

version = '0.1.0'

setuptools.setup(
    name = 'pyublox',
    version = version,
    description = 'Python UBlox tools',
    long_description = ('Libraries and utilities for working with uBlox GPS units'),
    url = 'https://github.com/tridge/pyUblox/',
    classifiers=['Development Status :: 4 - Beta',
                 'Environment :: Console',
                 'Intended Audience :: Science/Research',
                 'License :: OSI Approved :: GNU General Public License v3 (GPLv3)', # TBC with tridge!  No license exists at
                 'Operating System :: OS Independent',
                 'Programming Language :: Python :: 2.7',
                 'Programming Language :: Python :: 3.5',
                 'Topic :: Scientific/Engineering'
    ],
    license='GPLv3',
    packages = [ 'ublox',
                 'ublox.util',
    ],
    install_requires=[
        'future',
    ],
    entry_points = {
        "console_scripts": [
        ],
    },
)
