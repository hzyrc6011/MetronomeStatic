import json
import os
from PyBirdViewCode.clang_utils.code_attributes.utils import get_func_decl, parse_file
from PyBirdViewCode.uast import ClangASTConverter
from PyBirdViewCode.uast.universal_ast_nodes import SourceElement
from PyBirdViewCode.uast.universal_cfg_extractor import CFGBuilder
from PyBirdViewCode.utils.files import FileManager, abspath_from_file
from tests.base import asset_path
from PyBirdViewCode.clang_utils import beautified_print_ast
from PyBirdViewCode.uml_utils.SequenceDiagram import ast_to_diagram
import networkx as nx

file_manager = FileManager(abspath_from_file("output", __file__))


def test_cfg_extraction_error_handling():
    file = asset_path("uml/sequence-diagram.c")
    evaluator = ClangASTConverter()
    cursor = get_func_decl(
        parse_file(
            file,
        ).cursor,
        "func1",
    )
    assert cursor is not None

    beautified_print_ast(cursor, "out.json")
    ret = evaluator.eval(cursor)

    # print(cb.print_graph())
    file_manager.json_dump(ret.to_dict(), "handle-error-demo.json")

    ast_to_diagram(ret, file_manager.get_abspath("handling-errors.plantuml"))
