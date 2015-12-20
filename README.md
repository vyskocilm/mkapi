# mkapi

## About

Create zproject api models from header files declarations.

## How to use

`mkapi.py` needs [pycparser](https://github.com/eliben/pycparser/) installed. Use your package manager or pip to install it.

Test of functionality is done on headers from [czmq](https://github.com/zeromq/czmq/). In order to make it work, you need [fake_libc_include](https://github.com/eliben/pycparser/tree/master/utils/fake_libc_include), which adds necessary declarations. However `fake_libc_include` is not a part of Python packages.

Usage is simple. Change dir to `tests/czmq` and run `python ../../mkapi.py -I/path/to/fake_libc_include include/czmq.h`. Result models will be in `api/` directory.
