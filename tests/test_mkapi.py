# test for mkapi.py script
# use py.test from root directory to run it

from __future__ import print_function

import glob
import os
import re
import shutil
import sys

from xml.etree import ElementTree as ET

sys.path.insert(0, os.getcwd())
from mkapi import main

def mkapi():

    args = list()

    for p in ("pycparser", os.getcwd(), "/usr/share/python-pycparser/"):
        p = os.path.join(p, "fake_libc_include")
        if os.path.isdir(p):
            args.extend(("-I",  p))
            break

    if os.path.isdir("api"):
        shutil.rmtree("api")
    args.append("include/czmq.h")
    main(args)

def c(text):
    return text.replace(' ', '_')

IGNORE_TEXT = 0x01

WHSPC_RE = re.compile(r'\W+')
DESTROY_COMMENT_RE = re.compile(r'The caller is responsible for destroying the return value when finished with it')
def s_strip(text):
    ret = re.sub(WHSPC_RE, ' ', text)
    ret = re.sub(DESTROY_COMMENT_RE, '', ret)
    return ret.strip()

def s_cmp_element(orig, new, orig_f, new_f, ignore=0):

    assert(orig.tag == new.tag)

    orig_dict = dict( (k, c(v)) for k, v in orig.items() )
    new_dict = dict(new.items())

    # accrding ML the semantics is not clear, so ignore it in the test
    if "polymorphic" in orig_dict:
        orig_dict["singleton"] = "1"
        del orig_dict["polymorphic"]
    if "polymorphic" in new_dict:
        new_dict["singleton"] == "1"
        del orig_dict["polymorphic"]

    try:
        assert(orig_dict == new_dict)
    except AssertionError as ae:
        print("Error in processing file '%s', tag: '%s' name = '%s'" % (
            os.path.basename(orig_f), orig.tag, orig.get("name")), file=sys.stderr)
        print ("orig.items(): %s, new.items(): %s" % (orig, new))
        raise ae

    if (ignore & IGNORE_TEXT != IGNORE_TEXT):
        if orig.text is None and new.text is None:
            return
        try:
            assert(s_strip(orig.text) == s_strip(new.text))
        except AssertionError as ae:
            print("Error in processing file '%s', tag: '%s' name = '%s'" % (
                os.path.basename(orig_f), orig.tag, orig.get("name")), file=sys.stderr)
            import pdb; pdb.set_trace()
            raise ae

def s_find_new(root, nodes_new_find, orig):
    orig_name = orig.get("name").replace(' ', '_')
    for new in root.findall(nodes_new_find):
        if new.tag == orig.tag and new.get("name") == orig_name:
            return new
    raise ValueError("<%s name='%s' /> not found in new nodes" % (nodes_new_find, orig.get("name")))

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

    for name in ("callback_type", "method"):
        for orig_n in root_orig.findall(name):
            if orig_n.get("exclude") == "1":
                continue
            try:
                new_n = s_find_new(root_new, name, orig_n)
            except ValueError as ve:
                print("Error reading '%s': %s" % (orig, ve))
                raise ve
            s_cmp_element(
                    orig_n,
                    new_n,
                    orig,
                    new)

def test_mkapi():
    oldcwd = os.getcwdu()
    os.chdir("tests/czmq")

    mkapi()
    for orig in glob.glob("api.orig/*.xml"):
        new = orig.replace("api.orig", "api")
        assert(os.path.exists(new))

        cmp_xml(orig, new)

    os.chdir(oldcwd)
