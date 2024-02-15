from setuptools import setup, find_packages

setup(
    name='garden',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click',
        'requests',
        'tabulate',
    ],
    entry_points='''
        [console_scripts]
        garden=garden.cli:cli
    ''',
)

