"""
Evaluate AST generated by libclang.

The evaluation input can be either concrete value or z3 symbolic variable.
"""

from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    TypeVar,
    TypedDict,
    Union,
)

from clang.cindex import (
    Cursor,
    CursorKind,
    SourceLocation,
    TypeKind,
    Type as CindexType,
)

from ..clang_utils.code_attributes.extract_data_structure import (
    FunctionDefModel,
)


from ..clang_utils.code_attributes import (
    UnaryOpPos,
    extract_literal_value,
    split_binary_operator,
    split_for_loop_conditions,
    split_unary_operator,
    split_compound_assignment,
    traversal_with_callback,
    is_function_definition,
    beautified_print_ast,
)
from ..utils import MelodieGenerator
from ..uast import universal_ast_nodes as nodes
from ..uast import universal_ast_types as types

if TYPE_CHECKING:
    CursorKind: Any = CursorKind

T = TypeVar("T")


def filter_cursor_children(
    c: Cursor, cond: Callable[[Cursor], bool]
) -> MelodieGenerator[Cursor]:
    return MelodieGenerator(c.get_children()).filter(cond)


def get_cursor_child(c: Cursor, cond: Callable[[Cursor], bool]) -> Optional[Cursor]:
    ret = MelodieGenerator(c.get_children()).filter(cond).to_list()
    if len(ret) == 0:
        return None
    else:
        return ret[0]


def first_child(c: Cursor) -> Cursor:
    return next(c.get_children())


def ensure_not_none(val: Optional[T]) -> T:
    assert val is not None
    return val


class LabelDesc(TypedDict):
    parent_offset: int
    label: str
    index: int


class ClangASTConverter:
    def __init__(
        self,
    ) -> None:
        self.source_location_filter: Optional[Callable[[SourceLocation], bool]] = None
        self.platform_default_bits: Dict[
            Literal["int", "char", "short", "long", "longlong", "float", "double"], int
        ] = {
            "int": 32,
            "long": 32,
            "longlong": 64,
            "short": 16,
            "char": 8,
            "float": 32,
            "double": 64,
        }
        self._handlers_map: Dict[
            CursorKind, Callable[[Cursor], nodes.SourceElement]
        ] = {
            # TRANSLATIONS
            CursorKind.TRANSLATION_UNIT: lambda c: nodes.CompilationUnit(
                self.eval_children(c)
            ),
            CursorKind.CXX_METHOD: self._handle_cxx_method,
            CursorKind.CXX_ACCESS_SPEC_DECL: self._handle_cxx_access_spec_decl,
            # TEMPLATES
            CursorKind.TYPE_ALIAS_TEMPLATE_DECL: self._handle_notimplemented,
            CursorKind.TYPE_ALIAS_DECL: self._handle_notimplemented,
            CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION: self._handle_notimplemented,
            CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION: self._handle_notimplemented,
            CursorKind.FUNCTION_TEMPLATE: self._handle_notimplemented,
            # CXX
            CursorKind.CXX_BASE_SPECIFIER: self._handle_notimplemented,
            CursorKind.CONSTRUCTOR: self._handle_notimplemented,
            # DECLARATIONS
            CursorKind.CLASS_DECL: self._handle_class_decl,
            CursorKind.ENUM_DECL: self._handle_enum_decl,
            CursorKind.STRUCT_DECL: self._handle_struct_decl,
            CursorKind.TYPEDEF_DECL: self._handle_typedef_decl,
            CursorKind.FIELD_DECL: self._handle_field_decl,
            CursorKind.UNION_DECL: self._handle_union_decl,
            CursorKind.DECL_STMT: lambda c: nodes.CompoundDecl(self.eval_children(c)),
            CursorKind.VAR_DECL: self._handle_var_decl,
            CursorKind.PARM_DECL: self._handle_parm_decl,
            CursorKind.UNEXPOSED_DECL: self._handle_notimplemented,
            CursorKind.FUNCTION_DECL: self._handle_function_decl,
            CursorKind.ASM_STMT: self._handle_notimplemented,
            CursorKind.NAMESPACE: self._handle_namespace,
            # ATTRIBUTES
            CursorKind.UNEXPOSED_ATTR: self._handle_notimplemented,
            CursorKind.DLLIMPORT_ATTR: self._handle_notimplemented,
            CursorKind.PURE_ATTR: self._handle_notimplemented,
            # EXPRESSIONS
            CursorKind.DECL_REF_EXPR: lambda c: (
                nodes.Name(c.spelling) if c.spelling else self.eval_children(c)[0]
            ),
            CursorKind.MEMBER_REF_EXPR: self._handle_member_ref_expr,
            CursorKind.ARRAY_SUBSCRIPT_EXPR: self._handle_array_subscript_expr,
            CursorKind.UNEXPOSED_EXPR: self._handle_unexposed_expr,
            CursorKind.CSTYLE_CAST_EXPR: lambda c: self._handle_cast_expr(c, "c"),
            CursorKind.CXX_STATIC_CAST_EXPR: lambda c: self._handle_cast_expr(
                c, "cxx_static"
            ),
            CursorKind.PAREN_EXPR: lambda c: self.eval_children(c)[0],
            CursorKind.INIT_LIST_EXPR: self._handle_init_list_expr,
            CursorKind.CALL_EXPR: self._handle_call_expr,
            CursorKind.CXX_UNARY_EXPR: self._handle_cxx_unary_expr,
            CursorKind.CONDITIONAL_OPERATOR: self._handle_conditional_operator,
            CursorKind.ADDR_LABEL_EXPR: self._handle_addr_label_expr,
            CursorKind.CLASS_TEMPLATE: self._handle_notimplemented,
            CursorKind.USING_DIRECTIVE: lambda c: nodes.Using(
                self.eval_single_cursor(next(c.get_children()))
            ),
            CursorKind.USING_DECLARATION: lambda c: nodes.Using(
                self.eval_single_cursor(next(c.get_children()))
            ),
            CursorKind.OVERLOADED_DECL_REF: lambda c: nodes.Name(c.spelling),
            CursorKind.NAMESPACE_REF: lambda c: nodes.NameSpaceRef(c.spelling),
            # TYPES
            CursorKind.TYPE_REF: lambda c: nodes.Type(c.spelling),
            # LITERALS
            CursorKind.INTEGER_LITERAL: lambda c: nodes.Literal(
                ensure_not_none(extract_literal_value(c)), "int"
            ),
            CursorKind.STRING_LITERAL: lambda c: nodes.Literal(
                ensure_not_none(extract_literal_value(c)), "str"
            ),
            CursorKind.CXX_BOOL_LITERAL_EXPR: lambda c: nodes.Literal(
                ensure_not_none(extract_literal_value(c)), "bool"
            ),
            CursorKind.FLOATING_LITERAL: lambda c: nodes.Literal(
                ensure_not_none(extract_literal_value(c)), "float"
            ),
            # OPERATORS
            CursorKind.BINARY_OPERATOR: self._handle_binary_operator,
            CursorKind.UNARY_OPERATOR: self._handle_unary_operator,
            CursorKind.COMPOUND_ASSIGNMENT_OPERATOR: self._handle_compound_assignment_operator,
            # STATEMENTS
            CursorKind.WARN_UNUSED_RESULT_ATTR: self._handle_notimplemented,
            CursorKind.COMPOUND_STMT: lambda c: nodes.BlockStmt(self.eval_children(c)),
            CursorKind.IF_STMT: self._handle_if_stmt,
            CursorKind.FOR_STMT: self._handle_for_stmt,
            CursorKind.GOTO_STMT: self._handle_goto_stmt,
            CursorKind.INDIRECT_GOTO_STMT: self._handle_indirect_goto_stmt,
            CursorKind.LABEL_STMT: self._handle_label_stmt,
            CursorKind.WHILE_STMT: self._handle_while_stmt,
            CursorKind.SWITCH_STMT: self._handle_switch_stmt,
            CursorKind.CASE_STMT: self._handle_case_stmt,
            CursorKind.DO_STMT: self._handle_do_stmt,
            CursorKind.BREAK_STMT: lambda c: nodes.BreakStmt(
                self.eval_single_cursor(next(c.get_children()))
                if len(list(c.get_children())) > 0
                else None
            ),
            CursorKind.NULL_STMT: self._handle_notimplemented,
            CursorKind.CONTINUE_STMT: lambda c: nodes.ContinueStmt(
                self.eval_single_cursor(next(c.get_children()))
                if len(list(c.get_children())) > 0
                else None
            ),
            # CursorKind.GOTO_STMT: lambda c: None,
            # CursorKind.CASE_STMT: lambda c: None,
            CursorKind.RETURN_STMT: self._handle_return_stmt,
        }

        # Return value of execution
        self._ret_value = None
        self._labels: Dict[str, LabelDesc] = {}

        int_bits = self.platform_default_bits["int"]
        char_bits = self.platform_default_bits["char"]
        short_bits = self.platform_default_bits["short"]
        long_bits = self.platform_default_bits["long"]
        long_long_bits = self.platform_default_bits["longlong"]
        float_bits = self.platform_default_bits["float"]
        double_bits = self.platform_default_bits["double"]
        self.integer_types_mapping = {
            TypeKind.CHAR_U: nodes.IntType(char_bits, False),
            TypeKind.UCHAR: nodes.IntType(char_bits, False),
            TypeKind.CHAR16: nodes.IntType(16),
            TypeKind.CHAR32: nodes.IntType(32),
            TypeKind.USHORT: nodes.IntType(short_bits, False),
            TypeKind.UINT: nodes.IntType(int_bits, False),
            TypeKind.ULONG: nodes.IntType(long_bits, False),
            TypeKind.ULONGLONG: nodes.IntType(long_long_bits, False),
            TypeKind.UINT128: nodes.IntType(128, False),
            TypeKind.CHAR_S: nodes.IntType(char_bits),
            TypeKind.SCHAR: nodes.IntType(char_bits),
            TypeKind.WCHAR: nodes.IntType(16),
            TypeKind.SHORT: nodes.IntType(short_bits),
            TypeKind.INT: nodes.IntType(int_bits),
            TypeKind.LONG: nodes.IntType(long_bits),
            TypeKind.LONGLONG: nodes.IntType(long_long_bits),
            TypeKind.INT128: nodes.IntType(128),
        }
        self.float_kinds_mapping = {
            TypeKind.FLOAT: nodes.FloatType(32),
            TypeKind.DOUBLE: nodes.FloatType(double_bits),
            TypeKind.LONGDOUBLE: nodes.FloatType(64),
        }

    def convert_type(self, t: CindexType) -> nodes.DATA_TYPE:
        if 4 <= t.kind.value <= 20:
            return self.integer_types_mapping.get(t.kind, nodes.UnknownType(t.spelling))
        elif t.kind == TypeKind.CONSTANTARRAY:
            return nodes.ArrayType(
                self.convert_type(t.get_array_element_type()), t.get_array_size()
            )
        elif t.kind in self.float_kinds_mapping:
            return self.float_kinds_mapping.get(t.kind, nodes.UnknownType(t.spelling))
        elif t.kind == TypeKind.ELABORATED:
            return nodes.UserDefinedType(t.spelling)
        elif t.kind == TypeKind.POINTER:
            return nodes.AddrReferenceType(self.convert_type(t.get_pointee()))
        elif t.kind == TypeKind.VOID:
            return nodes.VoidType()
        else:
            print("kind", t.kind, t.spelling)
            return nodes.UnknownType(t.spelling)

    def _handle_notimplemented(self, c: Cursor) -> nodes.NotImplementedItem:
        return nodes.NotImplementedItem(str(c.kind))

    def _calc_reference_expression(self, c: Cursor) -> nodes.ReferenceExpr:
        referenced_variable = self.eval_single_cursor(c)
        return nodes.ReferenceExpr(referenced_variable)

    def _calc_dereference_expression(self, c: Cursor) -> nodes.DereferenceExpr:
        result = self.eval_single_cursor(c)
        return nodes.DereferenceExpr(result)

    def eval_single_cursor_if_not_none(self, cursor: Optional[Cursor]):
        return self.eval_single_cursor(cursor) if cursor is not None else None

    def eval_single_cursor(self, cursor: Cursor):
        try:
            ret = self._handlers_map[cursor.kind](cursor)
            if cursor is not None and ret is not None:
                ret.location = (cursor.location.line, cursor.location.column)

            return ret
        except Exception as e:
            if cursor is not None:
                print(
                    "error occurred in cursor",
                    cursor.location.file,
                    cursor.location.line,
                    cursor.location.column,
                )
            raise e

    def eval_children(self, cursor: Cursor) -> List:
        children_values = []
        for child in cursor.get_children():
            if self.source_location_filter is not None and (
                not self.source_location_filter(child)
            ):
                continue
            children_values.append(self.eval_single_cursor(child))
        return children_values

    def eval(self, cursor: Cursor) -> nodes.SourceElement:
        # try:
        return self.eval_single_cursor(cursor)
        # except FunctionReturn as e:

    def _handle_unexposed_expr(self, cursor: Cursor) -> nodes.SourceElement:
        children_values = self.eval_children(cursor)
        if len(children_values) == 1:
            return children_values[0]
        else:
            return nodes.SpecialExpr("unexposed", children_values)

    def _handle_cxx_access_spec_decl(self, cursor: Cursor) -> nodes.AccessSpecfier:
        tokens = [t.spelling for t in cursor.get_tokens()]
        assert tokens[0] in ("public", "private", "protected")
        return nodes.AccessSpecfier(tokens[0])

    def _handle_cxx_method(self, cursor: Cursor) -> nodes.MethodDecl:
        decl = self._handle_function_decl(cursor)

        type_ref_cursor = get_cursor_child(
            cursor, lambda c: c.kind == CursorKind.TYPE_REF
        )
        type_ref = self.eval_single_cursor_if_not_none(type_ref_cursor)
        decl.type_ref = type_ref
        return decl

    def _handle_function_decl(self, cursor: Cursor) -> nodes.MethodDecl:
        params_ast = (
            filter_cursor_children(cursor, lambda c: c.kind == CursorKind.PARM_DECL)
            .map(self.eval_single_cursor)
            .l
        )

        body_cursor = get_cursor_child(
            cursor, lambda c: c.kind == CursorKind.COMPOUND_STMT
        )
        body_ast = self.eval_single_cursor_if_not_none(body_cursor)
        return_type = self.convert_type(cursor.type.get_result())
        return nodes.MethodDecl(
            nodes.Name(cursor.spelling),
            nodes.MethodType(params_ast, return_type, []),
            body_ast,
        )

    def _handle_cast_expr(
        self, cursor: Cursor, kind: Literal["c", "cxx_static"]
    ) -> nodes.CastExpr:
        child = next(cursor.get_children())
        return nodes.CastExpr(
            self.convert_type(cursor.type),
            self.convert_type(child.type),
            self.eval_single_cursor(child),
            kind,
        )

    def _handle_class_decl(self, cursor: Cursor) -> Optional[nodes.ClassDecl]:
        # class_name = curs
        cls_decl = nodes.ClassDecl(
            cursor.spelling, self.eval_children(cursor), [], [], []
        )
        return cls_decl

    def _handle_enum_decl(self, cursor: Cursor) -> Optional[nodes.EnumDecl]:
        # import pdb; pdb.set_trace()
        enum_children = []
        child: Cursor
        for child in cursor.get_children():
            enum_children.append(nodes.EnumConst(child.spelling, child.enum_value))
        return nodes.EnumDecl(cursor.spelling, enum_children)

    def _handle_struct_decl(self, cursor: Cursor) -> Optional[nodes.StructDecl]:
        assert cursor.kind == CursorKind.STRUCT_DECL, "Expected a STRUCT_DECL cursor"

        m = nodes.StructDecl(cursor.spelling, [])

        for child in cursor.get_children():
            m.fields.append(self.eval_single_cursor(child))

        return m

    def _handle_union_decl(self, cursor: Cursor) -> Optional[nodes.UnionDecl]:
        assert cursor.kind == CursorKind.UNION_DECL, "Expected a UNION_DECL cursor"

        m = nodes.UnionDecl(cursor.spelling, [])

        for child in cursor.get_children():
            m.children.append(self.eval_single_cursor(child))

        return m

    def _handle_typedef_decl(self, cursor: Cursor) -> nodes.Type:
        children = list(cursor.get_children())

        child: Optional[nodes.SourceElement] = (
            self.eval_single_cursor(children[0]) if len(children) > 0 else None
        )
        # import pdb

        # pdb.set_trace()
        return nodes.Type(cursor.spelling, child)

    def _handle_field_decl(self, cursor: Cursor) -> nodes.FieldDecl:
        assert cursor.kind == CursorKind.FIELD_DECL
        children: List[Cursor] = list(cursor.get_children())
        init_value: Optional[str] = None
        if len(children) == 1:
            init_value = extract_literal_value(children[0])

        return nodes.FieldDecl(
            cursor.spelling, self.convert_type(cursor.type), init_value
        )

    def _handle_parm_decl(self, cursor: Cursor) -> nodes.ParamDecl:
        return nodes.ParamDecl(cursor.spelling, self.convert_type(cursor.type))

    def _handle_var_decl(
        self, cursor: Cursor
    ) -> Union[nodes.VarDecl, nodes.Assignment]:
        children_asts = (
            MelodieGenerator(cursor.get_children())
            .filter(lambda c: c.kind not in (CursorKind.TYPE_REF,))
            .l
        )
        children_parsed = self.eval_children(cursor)

        # Handle the vardecl storing a function pointer
        # if all(map(lambda x: isinstance(x, nodes.ParamDecl), children_parsed)):
        if cursor.type.kind == TypeKind.POINTER:
            func_type = cursor.type.get_pointee()
            if func_type.kind == TypeKind.FUNCTIONPROTO:
                return_type = func_type.get_result().spelling
                return nodes.VarDecl(
                    cursor.spelling,
                    None,
                    nodes.MethodType(children_parsed, return_type),
                )
        if len(children_asts) >= 1:
            l_value = nodes.Name(cursor.spelling)
            r_value = self.eval_single_cursor(children_asts[-1])
            return nodes.VarDecl(l_value, r_value, self.convert_type(cursor.type))
        else:
            l_value = nodes.Name(cursor.spelling)
            return nodes.VarDecl(l_value, None, self.convert_type(cursor.type))

    def _handle_member_ref_expr(self, cursor: Cursor) -> nodes.FieldAccessExpr:
        children = list(cursor.get_children())
        referenced_variable = (
            self.eval_single_cursor(children[0]) if len(children) > 0 else None
        )
        return nodes.FieldAccessExpr(cursor.spelling, referenced_variable)

    def _handle_array_subscript_expr(self, cursor: Cursor) -> nodes.ArrayAccessExpr:
        array_ref_ast, indexer_ast = cursor.get_children()
        array = self.eval_single_cursor(array_ref_ast)
        index: int = self.eval_single_cursor(indexer_ast)
        return nodes.ArrayAccessExpr(index, array)

    def _handle_unary_operator(self, cursor: Cursor) -> nodes.UnaryExpr:
        op, operand, pos = split_unary_operator(cursor)
        return nodes.UnaryExpr(
            op, self.eval_single_cursor(operand), pos == UnaryOpPos.BEFORE
        )

    def _handle_binary_operator(
        self, cursor: Cursor
    ) -> Union[nodes.Assignment, nodes.BinaryExpr]:
        l_ast, symbol, r_ast = split_binary_operator(cursor)
        if symbol == "=":
            return nodes.Assignment(
                "=", [self.eval_single_cursor(l_ast)], [self.eval_single_cursor(r_ast)]
            )
        else:
            value_left, value_right = self.eval_children(cursor)
            return nodes.BinaryExpr(symbol, value_left, value_right)

    def _handle_compound_assignment_operator(self, cursor: Cursor) -> nodes.Assignment:
        l_value, op, r_value = split_compound_assignment(cursor)
        return nodes.Assignment(
            op, [self.eval_single_cursor(l_value)], [self.eval_single_cursor(r_value)]
        )

    def _handle_call_expr(self, cursor: Cursor) -> nodes.CallExpr:
        children = list(cursor.get_children())
        if len(children) == 0:
            return None
        callee_ast, *args_ast = children
        arg_values = [self.eval_single_cursor(item) for item in args_ast]
        callee_value = self.eval_single_cursor(callee_ast)
        return nodes.CallExpr(callee_value, arg_values)

    def _handle_cxx_unary_expr(self, cursor: Cursor) -> nodes.SpecialExpr:
        tokens = [
            t.spelling for t in cursor.get_tokens() if t.spelling not in ("(", ")")
        ]

        # handle sizeof
        if tokens[0] == "sizeof":
            return nodes.SpecialExpr("sizeof", tokens[1:])
        else:
            raise NotImplementedError

    def _handle_conditional_operator(self, cursor: Cursor) -> nodes.Conditional:
        pred, if_true, if_false = self.eval_children(cursor)
        return nodes.Conditional(pred, if_true, if_false)

    def _handle_addr_label_expr(self, cursor: Cursor) -> nodes.AddressLabel:
        return nodes.AddressLabel(cursor.spelling)

    def _handle_init_list_expr(self, cursor: Cursor) -> nodes.ArrayInitializer:
        children_values = self.eval_children(cursor)
        return nodes.ArrayInitializer(children_values)

    def _handle_if_stmt(self, cursor: Cursor) -> nodes.IfThenElseStmt:
        children: List[Cursor] = list(cursor.get_children())
        condition_ast = children[0]
        assert len(children) in (2, 3)
        if len(children) == 2:
            return nodes.IfThenElseStmt(
                self.eval_single_cursor(condition_ast),
                self.eval_single_cursor(children[1]),
            )
        elif len(children) == 3:
            return nodes.IfThenElseStmt(
                self.eval_single_cursor(condition_ast),
                self.eval_single_cursor(children[1]),
                self.eval_single_cursor(children[2]),
            )
        else:
            raise NotImplementedError(len(children))

    def _handle_namespace(self, cursor: Cursor):
        return nodes.NameSpaceDef(cursor.spelling, self.eval_children(cursor))

    def _handle_goto_stmt(self, cursor: Cursor):

        return nodes.GoToStmt(next(cursor.get_children()).spelling)

    def _handle_indirect_goto_stmt(self, cursor: Cursor):
        return nodes.GoToStmt(
            self.eval_single_cursor(next(cursor.get_children())), direct=False
        )

    def _handle_label_stmt(self, cursor: Cursor):
        return nodes.Label(
            cursor.spelling, self.eval_single_cursor(next(cursor.get_children()))
        )

    def _handle_while_stmt(self, cursor: Cursor):
        cond_ast, body_ast = self.eval_children(cursor)
        return nodes.WhileStmt(cond_ast, body_ast)

    def _handle_switch_stmt(self, cursor: Cursor) -> nodes.SwitchStmt:
        condition_cursor, switch_body_cursor = cursor.get_children()
        assert switch_body_cursor.kind == CursorKind.COMPOUND_STMT
        switch_body_item_cursor: Cursor
        switch_cases: List[nodes.SwitchCase] = []
        default_procedure = None
        # Get switch items from body cursor
        for switch_body_item_cursor in switch_body_cursor.get_children():
            if switch_body_item_cursor.kind == CursorKind.CASE_STMT:
                case_cond, body = self.eval_children(switch_body_item_cursor)
                switch_cases.append(nodes.SwitchCase([case_cond], body))
            elif switch_body_item_cursor.kind == CursorKind.DEFAULT_STMT:
                body = self.eval_children(switch_body_item_cursor)[0]
                switch_cases.append(nodes.SwitchCase([nodes.DefaultStmt()], body))
            elif switch_body_item_cursor.kind in (CursorKind.BREAK_STMT,):
                if not isinstance(switch_cases[-1].body, nodes.BlockStmt):
                    switch_cases[-1].body = nodes.BlockStmt([switch_cases[-1].body])
                if switch_body_item_cursor.kind == CursorKind.BREAK_STMT:
                    switch_cases[-1].body.statements.append(
                        self.eval_single_cursor(switch_body_item_cursor)
                    )
            else:
                raise NotImplementedError
        return nodes.SwitchStmt(self.eval_single_cursor(condition_cursor), switch_cases)

    def _handle_case_stmt(self, cursor: Cursor) -> nodes.SwitchCase:
        case_cond, body = self.eval_children(cursor)
        return nodes.SwitchCase([case_cond], body)

    def _handle_do_stmt(self, cursor: Cursor):
        body_ast, pred_ast = self.eval_children(cursor)
        return nodes.DoWhileStmt(pred_ast, body_ast)

    def _handle_for_stmt(self, cursor: Cursor):
        stmt1_cursor, cond_expr_cursor, stmt2_cursor, body_cursor = (
            split_for_loop_conditions(cursor)
        )
        # if stmt1_cursor is not None:
        stmt1_ast = self.eval_single_cursor(stmt1_cursor) if stmt1_cursor else None
        # if stmt2_cursor is not None:
        stmt2_ast = self.eval_single_cursor(stmt2_cursor) if stmt2_cursor else None
        # if cond_expr_cursor is not None:
        cond_ast = (
            self.eval_single_cursor(cond_expr_cursor) if cond_expr_cursor else None
        )
        # if body_cursor is not None:
        body_ast = self.eval_single_cursor(body_cursor) if body_cursor else None
        return nodes.ForStmt(stmt1_ast, cond_ast, stmt2_ast, body_ast)

    def _handle_return_stmt(self, cursor: Cursor) -> nodes.ReturnStmt:
        children_values = self.eval_children(cursor)
        if len(children_values) > 0:
            val = children_values[0]
            return nodes.ReturnStmt([val])
        else:
            return nodes.ReturnStmt()

    def get_func(self, c: Cursor) -> Tuple[Cursor, FunctionDefModel]:
        if c.kind == CursorKind.DECL_REF_EXPR:
            return self._program_info.get_function_ast(
                c.spelling
            ), self._program_info.get_function_structure(c.spelling)
        elif c.kind == CursorKind.UNEXPOSED_EXPR:
            return self.get_func(first_child(c))
        else:
            raise KeyError(c.kind)

    def is_concrete_value(self, value: Any) -> bool:
        if isinstance(value, (int, float, bool, str)) or value is None:
            return True
        else:
            return False
