# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open('requirements.txt') as f:
	install_requires = f.read().strip().split('\n')

# get version from __version__ variable in german_accounting/__init__.py
from german_accounting import __version__ as version

setup(
	name='german_accounting',
	version=version,
	description='Reports for German Accounting like BWA, USt-VA etc.',
	author='LIS',
	author_email='mtraeber@linux-ag.com',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
