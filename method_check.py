import sys
import os
import json
from collections import defaultdict

import clang.cindex
from pprint import pprint
from clang.cindex import *


def count_method_length(cursor):
    start_line = cursor.extent.start.line
    end_line = cursor.extent.end.line+1
    return end_line - start_line


def is_function_like(node):
    kinds = [CursorKind.CXX_METHOD, CursorKind.FUNCTION_DECL, CursorKind.CONSTRUCTOR, CursorKind.DESTRUCTOR]
    return node.kind in kinds

def count_conditional(node, parent):
    parent_kind = [CursorKind.IF_STMT, CursorKind.WHILE_STMT, CursorKind.FOR_STMT]
    if parent is not None and parent.kind in parent_kind and CursorKind.BINARY_OPERATOR == node.kind:
        tokens = [t.spelling for t in node.get_tokens()]
        return len(filter(lambda t: t in ["&&", "||"], tokens))

    return 0


def matches_filename(node, filename):
    return node.location.file is not None and filename in node.location.file.name


def method_definitions(cursor, filename):
    for node in cursor.walk_preorder():
        if not matches_filename(node, filename):
            continue
        if not is_function_like(node):
            continue
        if CursorKind.CXX_METHOD == node.kind and not node.is_definition():
            continue
        yield node


def fully_qualified(c):
    if c is None or c.kind == CursorKind.TRANSLATION_UNIT:
        return ''
    else:
        res = fully_qualified(c.semantic_parent)
        if res != '':
            return res + '::' + c.spelling
        return c.spelling


def count_depth(node, depth=0):
    depths = [depth]
    for c in node.get_children():
        if CursorKind.COMPOUND_STMT == node.kind:
            d = count_depth(c, depth+1)
        else:
            d = count_depth(c, depth)
        depths.append(d)
    return max(depths)



def cyclomatic(node, parent = None):
    count = 0

    count += count_conditional(node, parent)

    if CursorKind.COMPOUND_STMT == node.kind:
        count += 1

    for c in node.get_children():
        count += cyclomatic(c, node)

    return count
    

filenames = sys.argv[1:]

data = {}

for path in filenames:
    path = os.path.abspath(path)
    print("Processing {}".format(path))

    try:
        compdb = CompilationDatabase.fromDirectory("/Users/samueljackson/builds/mantid-main/")
        file_args = compdb.getCompileCommands(path)[0]
        file_args = list(file_args.arguments)[1:-1]
    except Exception, e:
        file_args = ['-x', 'c++']

    idx = Index.create()
    tu = idx.parse(path, file_args)

    defns = method_definitions(tu.cursor, os.path.basename(path))
    for defn in defns:
        name = fully_qualified(defn) + ":" + str(defn.extent.start.line) + ":" + str(defn.extent.start.column)
        location = defn.location.file.name
        meth_length = count_method_length(defn)
        meth_depth = count_depth(defn)
        complexity = cyclomatic(defn)
        data[name] = {'location': location, 'length':meth_length, 'depth':meth_depth, 'complexity':complexity}

with open('output.txt', 'w') as handle:
    json.dump(data, handle)
