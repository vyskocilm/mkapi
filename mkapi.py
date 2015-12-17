# licensed under MIT
# see LICENSE
from __future__ import print_function

import argparse
import re
import os
import sys

from collections import namedtuple
from xml.sax.saxutils import quoteattr as s_xml_quoteattr
from xml.sax.saxutils import escape as s_xml_escape

from pycparser import c_parser, c_ast, parse_file

__doc__ = """Generate zproto API XML model from CLASS compatible function declarations"""

MacroDecl = namedtuple("MacroDecl", "name, value, comment")
TypeDecl  = namedtuple("TypeDecl", "type, ptr")
ArgDecl   = namedtuple("ArgDecl", "name, type, ptr")

def s_parse_comments_and_macros(fp):

    interface_re = re.compile(r"^//\W*@interface\W*$")
    end_re = re.compile(r"^//\W*@end\W*$")
    macro_re = re.compile(r"^#define.*$")

    comments = dict()
    macros = list()

    is_interface = False
    last_comment = ""
    # go to @interface
    for i, line in enumerate(fp):
        if not is_interface:
            if not interface_re.match(line):
                continue
            is_interface = True
            continue

        if end_re.match(line):
            break

        if macro_re.match(line):
            try:
                _, name, value, comment = line.split(' ', 3)
                comment = comment.strip()[3:]
            except ValueError:
                _, name, value = line.split(' ', 2)
                value = value.strip()
                comment = ""
            macros.append(MacroDecl(name, value, comment))
            continue

        if line.startswith("//"):
            last_comment += line[2:].lstrip()
            continue

        if last_comment:
            comments[i] = last_comment
        last_comment = ""

    return comments, macros


def parse_comments_and_macros(filename):
    """Return comments, macros objects from file
    comments are tuple (line, comment)
    macros are (name, value, comment)

    Function use content between @interface @end lines only
    """

    with open(filename) as fp:
        return s_parse_comments_and_macros(fp)

class FuncDeclVisitor(c_ast.NodeVisitor):

    def __init__(self, *args, **kwargs):
        super(FuncDeclVisitor, self).__init__(*args, **kwargs)
        self._ret = list()

    @staticmethod
    def s_decl_type(node):
        ptr = ''

        while isinstance(node, c_ast.PtrDecl):
            ptr = ptr + '*'
            node = node.type

        for attr in ("names", "name"):
            if not hasattr(node.type, attr):
                continue
            return TypeDecl(' '.join(getattr(node.type, attr)), ptr)
        raise AttributeError("%s do not have .type.names or .type.name" % (node.__class__.__name__))

    @staticmethod
    def s_func_args(node):
        if node.args is None:
            return (ArgDecl('', "void", ''), )

        ret = list()
        for idx, n in node.args.children():
            if isinstance(n, (c_ast.Decl, c_ast.Typename)):
                typ, ptr = FuncDeclVisitor.s_decl_type(n.type)
                ret.append((ArgDecl(n.name, typ, ptr)))
            elif isinstance(n, c_ast.EllipsisParam):
                ret.append(ArgDecl("", "...", ""))
            else:
                raise NotImplementedError("%s is not supported in s_func_args" % (n.__class__.__name__))
        return tuple(ret)

    @staticmethod
    def s_decl_dict(node):
        decl_dict = {
                    "return_type" : FuncDeclVisitor.s_decl_type(node.type.type),
                    "name" : node.name,
                    "args" : FuncDeclVisitor.s_func_args(node.type),
                    "coord" : node.coord,
                    }
        return decl_dict

    def visit_Decl(self, node):
        if not isinstance (node.type, c_ast.FuncDecl):
            return
        decl_dict = FuncDeclVisitor.s_decl_dict(node)
        typ = "singleton"
        if  decl_dict["args"] and \
            decl_dict["args"][0].name in ("self", "self_p") and \
            decl_dict["args"][0].type.endswith("_t") and \
            decl_dict["args"][0].ptr == "*":
            typ = "method"
        decl_dict["type"] = typ
        self._ret.append(decl_dict)

    def visit_Typedef(self, node):
        if not isinstance(node.type, c_ast.FuncDecl):
            return
        decl_dict = FuncDeclVisitor.s_decl_dict(node)
        decl_dict["type"] = "callback_type"
        self._ret.append(decl_dict)

def s_cpp_args(args):
    cpp_args = list()
    try:
        for d in args.DEFINE:
            cpp_args.append("-D" + d)
    except TypeError:
        pass

    try:
        for d in args.INCLUDE:
            cpp_args.append("-I" + d)
    except TypeError:
        pass
    return cpp_args

def get_func_decls(filename, args):
    cpp_args = s_cpp_args(args)
    ast = parse_file(filename,
            use_cpp=True,
            cpp_path=os.path.join(os.path.dirname(__file__), "fake_cpp"),
            cpp_args=cpp_args)
    v = FuncDeclVisitor()
    for idx, node in ast.children():
        v.visit(node)
    return v._ret

def s_decl_to_zproto_type(arg):
    dct = {
            ("void", "*") : "anything",
            ("int", "")   : "integer",
            ("float", "") : "real",
            ("bool", "")  : "boolean",
            ("_Bool", "")  : "boolean",
            ("char", "*") : "string",
          }
    if arg.type.endswith("_t") and arg.ptr in ("*", "**"):
        return arg.type[:-2]
    return dct.get((arg.type, arg.ptr), arg.type)


def s_show_zproto_model_arguments(fp, decl_dict):
    for arg in decl_dict["args"]:
        if arg.name in ("self", "self_p") and arg.type != "void":
            continue
        print("""        <argument name = "%(name)s" type = "%(type)s"%(byref)s/>""" %
                {   "name" : arg.name,
                    "type" : s_decl_to_zproto_type(arg),
                    "byref" : """ by_reference="1" """ if arg.ptr == "**" else "",
                }, file=fp)

def s_show_zproto_mc(fp, klass_l, dct, comments):
    """Show method or callback_type - they're mostly the same except tag name"""
    typ = dct["type"]
    singleton=''
    if typ == "singleton":
        typ = "method"
        singleton=""" singleton = "1" """
    print("""    <%s name = "%s"%s>""" % (typ, dct["name"][klass_l:], singleton), file=fp)

    for i in range(3):
        if dct["coord"].line -i in comments:
            print(s_xml_escape(comments[dct["coord"].line-i]), file=fp)

    s_show_zproto_model_arguments(fp, dct)
    if dct["return_type"].type != "void":
        print("""        <return type = "%s" />""" % (s_decl_to_zproto_type(dct["return_type"])), file=fp)
    print("""    </%s>\n""" % (typ, ), file=fp)


def show_zproto_model(fp, klass, decls, comments, macros):
    print("""
<!--
    This model defines a public API for binding.
-->
<class name = "%s" >

    <include filename = "../license.xml" />
    """ % (klass, ), file=fp)

    klass_l = len(klass) + 1
    include = os.path.join("include", klass + ".h")

    for macro_decl in macros:
        print("""    <constant name = "%s" value = %s >%s</constant>\n""" % (
            macro_decl.name[klass_l:].lower(),
            s_xml_quoteattr(macro_decl.value),
            macro_decl.comment),
            file=fp)


    for decl_dict in (d for d in decls if d["coord"].file == include):
        if decl_dict["name"] == klass + "_new":
            print("""
    <!-- Constructor is optional; default one has no arguments -->
    <constructor>
        Create a new %s""" % (klass, ), file=fp)
            s_show_zproto_model_arguments(fp, decl_dict)
            print("""    </constructor>""", file=fp)
            continue

        if decl_dict["name"] == klass + "_destroy":
            print("""
    <!-- Destructor is optional; default one follows standard style -->
    <destructor />\n""", file=fp)
            continue

        s_show_zproto_mc(fp, klass_l, decl_dict, comments)

    print("</class>", file=fp)

def get_classes_from_decls(decls):
    seen = set()
    for decl_dict in decls:
        name = decl_dict["name"]
        klass = name[:name.rfind('_')]
        include = os.path.join("include", klass + ".h")
        if not os.path.exists(include):
            continue
        if klass in seen:
            continue
        seen.add(klass)
        yield klass

def main(argv=sys.argv[1:]):

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("header", help="main header file of the project")
    p.add_argument("--output", help="output directory for xml models, defaults to api.", default="api")
    p.add_argument("-D", "--define", help="", dest="DEFINE", action='append')
    p.add_argument("-I", "--include", help="", dest="INCLUDE", action='append')
    args = p.parse_args(argv)

    try:
        os.makedirs(args.output)
    except OSError as e:
        if e.errno != 17:   #file exists
            raise e

    decls = get_func_decls(args.header, args)
    for klass in get_classes_from_decls(decls):
        include = os.path.join("include", klass + ".h")
        comments, macros = parse_comments_and_macros(include)

        model = os.path.join(args.output, klass + ".xml")
        with open(model, 'wt') as fp:
            show_zproto_model(fp, klass, decls, comments, macros)

if __name__ == "__main__":
    main()
