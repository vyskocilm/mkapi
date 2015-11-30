# licensed under MIT
# see LICENSE
from __future__ import print_function

import argparse
import re
import os
import sys

from pycparser import c_parser, c_ast, parse_file

__doc__ = """Generate zproto API XML model from CLASS compatible function declarations"""

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
            _, name, value, comment = line.split(' ', 3)
            macros.append((name, value, comment.strip()[3:]))
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

        return (' '.join(node.type.names), ptr)

    @staticmethod
    def s_func_args(node):
        if node.args is None:
            return (('', "void", ''), )
        return [FuncDeclVisitor.s_decl_type(node.type) + (node.name, )
                for idx, node in node.args.children()]

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
        typ = "method"
        if not decl_dict["args"] or decl_dict["args"][0][2] not in ("self", "self_p"):
            typ = "singleton"
        decl_dict["type"] = typ
        self._ret.append(decl_dict)

    def visit_Typedef(self, node):
        if not isinstance(node.type, c_ast.FuncDecl):
            return
        decl_dict = FuncDeclVisitor.s_decl_dict(node)
        decl_dict["type"] = "callback"
        self._ret.append(decl_dict)

    def generic_visit(self, node):
        print('[GENERIC]: %s\n' % (node.__class__))
        node.show()
        print('\n')


def get_func_decls(filename):
    ast = parse_file(filename, use_cpp=True)
    v = FuncDeclVisitor()
    for idx, node in ast.children():
        v.visit(node)
    return v._ret

def show_c_decls(fp, decls):
    for decl_dict in decls:
        if decl_dict["type"] == "callback":
            print("[ERROR]: callback %s is not supported" % (decl_dict["name"]))
            continue
        print ("%(return_type)s %(name)s (%(args)s);\n" %
                {
                    "return_type" : ' '.join(decl_dict["return_type"]),
                    "name" : decl_dict["name"],
                    "args" : ', '.join(' '.join(x) for x in decl_dict["args"]),
                    }
                , file=fp)

def s_decl_to_zproto_type(arg):
    typ = arg[0]
    ptr = arg[1]
    dct = {
            ("void", "*") : "anything",
            ("int", "")   : "integer",
            ("float", "") : "real",
            ("bool", "")  : "boolean",
            ("_Bool", "")  : "boolean",
            ("char", "*") : "string",
          }
    if typ.endswith("_t") and ptr in ("*", "**"):
        return typ
    return dct.get((typ, ptr), typ)


def s_show_zproto_model_arguments(fp, decl_dict):
    for arg in decl_dict["args"]:
        if arg[2] == "self" or arg[2] == "self_p":
            continue
        print("""        <argument name = "%(name)s" type = "%(type)s"%(byref)s/>""" %
                {   "name" : arg[2],
                    "type" : s_decl_to_zproto_type(arg),
                    "byref" : """by_reference="1""" if arg[1] == "**" else "",
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
            print(comments[dct["coord"].line-i], file=fp)

    s_show_zproto_model_arguments(fp, dct)
    if dct["return_type"][0] != "void":
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

    for macro in macros:
        print("""    <constant name = "%s" value = "%s" >%s</constant>\n""" % (
            macro[0][klass_l:].lower(), macro[1], macro[2]), file=fp)


    for decl_dict in decls:
        if decl_dict["return_type"][0] == klass + "_t":
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
        klass = decl_dict["name"].split('_', 1)[0]
        if klass in seen:
            continue
        seen.add(klass)
        yield klass

def main(argv=sys.argv[1:]):

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("header", help="main header file of the project")
    p.add_argument("--output", help="output directory for xml models, defaults to api.", default="api")
    args = p.parse_args(argv)

    try:
        os.makedirs(args.output)
    except OSError as e:
        if e.errno != 17:   #file exists
            raise e

    decls = get_func_decls(args.header)
    #show_c_decls(decls)
    for klass in get_classes_from_decls(decls):
        include = os.path.join("include", klass + ".h")
        if not os.path.exists(include):
            print("E: '%s' does not exists, skipping" % (include, ))
            continue
        comments, macros = parse_comments_and_macros(include)

        model = os.path.join(args.output, klass + ".xml")
        with open(model, 'wt') as fp:
            show_zproto_model(fp, klass, decls, comments, macros)

if __name__ == "__main__":
    main()
