# test for mkapi.py script
# use py.test from root directory to run it

from __future__ import print_function

import glob
import os
import shutil
import subprocess
import sys

from xml.etree import ElementTree as ET

def mkapi():
    if not os.path.exists("../../mkapi.py"):
        raise NotImplementedError("../../mkkapi.py does not exists, and custom location are not supported!")

    if os.path.isdir("api"):
        shutil.rmtree("api")
    subprocess.check_call(["python", "../../mkapi.py", "include/czmq.h"])

def c(text):
    return text.replace(' ', '_')

IGNORE_TEXT = 0x01

def s_cmp_element(orig, new, orig_f, new_f, ignore=0):

    assert(orig.tag == new.tag)
    for (orig_key, orig_value), (new_key, new_value) in zip(orig.items(), new.items()):
        assert(orig_key == new_key)
        try:
            assert(c(orig_value) == new_value)
        except AssertionError as ae:
            print("Error in processing file '%s', tag: '%s'" % (
                os.path.basename(orig_f), orig.tag), file=sys.stderr)
            raise ae

    if (ignore & IGNORE_TEXT != IGNORE_TEXT):
        if orig.text is None and new.text is None:
            return
        try:
            assert(orig.text.strip() == new.text.strip())
        except AssertionError as ae:
            print("Error in processing file '%s', tag: '%s'" % (
                os.path.basename(orig_f), orig.tag), file=sys.stderr)

def s_find_new(new, nodes_new_find, orig):
    for new in new.find(nodes_new_find):
        if new.tag == orig.tag and new.get("name") == orig.get("name"):
            return new
    raise ValueError("<%s name='%s' /> not found in new nodes" % (node.tag, node.get("name")))

def cmp_xml(orig, new):
    try:
        root_orig = ET.parse(orig)
    except ET.ParseError as pe:
        print("Error in parsing '%s'" % orig)
        raise pe

    try:
        root_new = ET.parse(new)
    except ET.ParseError as pe:
        print("Error in parsing '%s'" % new)
        raise pe

    s_cmp_element(
            root_orig._root,
            root_new._root,
            orig,
            new,
            ignore = IGNORE_TEXT)

    for orig_n in root_orig.find("callback_type"):
        new_n = s_find_new(root_new, "callback_type", orig_n)
        s_cmp_element(
                orig_n,
                new_n,
                orig,
                new)

def test_mkapi():
    oldcwd = os.getcwdu()
    os.chdir("tests/fixtures")

    mkapi()
    for orig in glob.glob("api.orig/*.xml"):
        new = orig.replace("api.orig", "api")
        assert(os.path.exists(new))

        cmp_xml(orig, new)

    os.chdir(oldcwd)
