# licensed under MIT
# see LICENSE

from __future__ import print_function
import sys
from pycparser import c_parser, c_ast, parse_file

__doc__ = """
Read function and type declarations from header file and print them in zproto
api xml model.
"""

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

def show_c_decls(decls):
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
                )

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


def s_show_zproto_model_arguments(decl_dict):
    for arg in decl_dict["args"]:
        if arg[2] == "self" or arg[2] == "self_p":
            continue
        print("""        <argument name = "%(name)s" type = "%(type)s"%(byref)s/>""" %
                {   "name" : arg[2],
                    "type" : s_decl_to_zproto_type(arg),
                    "byref" : """by_reference="1""" if arg[1] == "**" else "",
                })

def s_show_zproto_mc(klass_l, dct):
    """Show method or callback_type - they're mostly the same except tag name"""
    typ = dct["type"]
    singleton=''
    if typ == "singleton":
        typ = "method"
        singleton="""singleton = "1" """
    print("""    <%s name = "%s"%s>""" % (typ, dct["name"][klass_l:], singleton))
    s_show_zproto_model_arguments(dct)
    if dct["return_type"][0] != "void":
        print("""        <return type = "%s" />""" % (s_decl_to_zproto_type(dct["return_type"])))
    print("""    </%s>\n""" % (typ, ))


def show_zproto_model(klass, decls):
    print("""
<!--
    This model defines a public API for binding.
-->
<class name = "%s" >

    <include filename = "../license.xml" />
    """ % (klass, ))

    klass_l = len(klass) + 1

    for decl_dict in decls:
        if decl_dict["return_type"][0] == klass + "_t":
            print("""
    <!-- Constructor is optional; default one has no arguments -->
    <constructor>
        Create a new %s""" % (klass, ))
            s_show_zproto_model_arguments(decl_dict)
            print("""    </constructor>""")
            continue

        if decl_dict["name"] == klass + "_destroy":
            print("""
    <!-- Destructor is optional; default one follows standard style -->
    <destructor />\n""")
            continue

        s_show_zproto_mc(klass_l, decl_dict)

    print("</class>")


def main(args=sys.argv):
    if len(sys.argv) <= 1:
        sys.exit(1)

    filename = sys.argv[1]
    decls = get_func_decls(filename)
    #show_c_decls(decls)
    show_zproto_model("myclass", decls)

if __name__ == "__main__":
    main()
