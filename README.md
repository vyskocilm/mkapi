# mkapi

## About

Create zproject api models from header files declarations.

## How to use

mkapi.py needs pycparser [https://github.com/eliben/pycparser/] with `fake_libc_include`, the git master version is recommended for parsing czmq.h.

Usage is simple - from root dir of zproject project run python `/path/to/mkapi.py -I/path/to/fake_libc_include include/main.h`. Result models will be in api/ directory.

For test you need to use py.test and run it from root directory. Tests will analyze czmq.h, put results to tests/fixtures/api/ and compare results with tests/fixtures/api.orig/
