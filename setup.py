from setuptools import setup, find_packages

setup(
    name='bull',
    version='0.1',
    author='Lars Kellogg-Stedman',
    author_email='lars@oddbit.com',
    url='https://github.com/larsks/bull',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'bull = bull.main:cli',
        ],
    }
)
