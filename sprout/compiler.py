from dataclasses import dataclass
from enum import Enum, auto

from . import ast
from .bytecode import Chunk, FunctionObject, OpCode
from .errors import CompileError
from .lexer import Lexer
from .parser import Parser
from .tokens import Token, TokenType


class FunctionType(Enum):
    SCRIPT = auto()
    FUNCTION = auto()


@dataclass(slots=True)
class Local:
    name: str
    depth: int


class Compiler:
    def __init__(self, name: str = "<script>", function_type: FunctionType = FunctionType.SCRIPT):
        self.function = FunctionObject(name)
        self.function_type = function_type
        self.scope_depth = 0
        self.locals = [Local("", 0)]

    @property
    def chunk(self) -> Chunk:
        return self.function.chunk

    def compile(self, statements: list[ast.Stmt]) -> FunctionObject:
        for statement in statements:
            self._statement(statement)
        self._emit_return(self._last_line(statements))
        return self.function

    def _statement(self, statement: ast.Stmt) -> None:
        if isinstance(statement, ast.Expression):
            self._expression(statement.expression)
            self._emit(OpCode.POP, self._expr_line(statement.expression))
        elif isinstance(statement, ast.Print):
            self._expression(statement.expression)
            self._emit(OpCode.PRINT, statement.line)
        elif isinstance(statement, ast.Let):
            self._let(statement)
        elif isinstance(statement, ast.Block):
            self._begin_scope()
            for child in statement.statements:
                self._statement(child)
            self._end_scope(self._last_line(statement.statements))
        elif isinstance(statement, ast.If):
            self._if(statement)
        elif isinstance(statement, ast.While):
            self._while(statement)
        elif isinstance(statement, ast.Function):
            self._function_declaration(statement)
        elif isinstance(statement, ast.Return):
            self._return(statement)
        else:
            raise CompileError(f"Unknown statement node {type(statement).__name__}.")

    def _expression(self, expression: ast.Expr) -> None:
        if isinstance(expression, ast.Literal):
            self._literal(expression)
        elif isinstance(expression, ast.Grouping):
            self._expression(expression.expression)
        elif isinstance(expression, ast.Unary):
            self._expression(expression.right)
            op = OpCode.NOT if expression.operator.type == TokenType.BANG else OpCode.NEGATE
            self._emit(op, expression.operator.line)
        elif isinstance(expression, ast.Binary):
            self._binary(expression)
        elif isinstance(expression, ast.Logical):
            self._logical(expression)
        elif isinstance(expression, ast.Variable):
            self._named_variable(expression.name, False)
        elif isinstance(expression, ast.Assign):
            self._expression(expression.value)
            self._named_variable(expression.name, True)
        elif isinstance(expression, ast.Call):
            self._expression(expression.callee)
            for argument in expression.arguments:
                self._expression(argument)
            self._emit(OpCode.CALL, expression.paren.line, len(expression.arguments))
        else:
            raise CompileError(f"Unknown expression node {type(expression).__name__}.")

    def _literal(self, expression: ast.Literal) -> None:
        if expression.value is None:
            self._emit(OpCode.NULL, expression.line)
        elif expression.value is True:
            self._emit(OpCode.TRUE, expression.line)
        elif expression.value is False:
            self._emit(OpCode.FALSE, expression.line)
        else:
            self._emit_constant(expression.value, expression.line)

    def _binary(self, expression: ast.Binary) -> None:
        self._expression(expression.left)
        self._expression(expression.right)
        direct = {
            TokenType.PLUS: OpCode.ADD,
            TokenType.MINUS: OpCode.SUBTRACT,
            TokenType.STAR: OpCode.MULTIPLY,
            TokenType.SLASH: OpCode.DIVIDE,
            TokenType.EQUAL_EQUAL: OpCode.EQUAL,
            TokenType.GREATER: OpCode.GREATER,
            TokenType.LESS: OpCode.LESS,
        }
        token_type = expression.operator.type
        if token_type in direct:
            self._emit(direct[token_type], expression.operator.line)
        elif token_type == TokenType.BANG_EQUAL:
            self._emit(OpCode.EQUAL, expression.operator.line)
            self._emit(OpCode.NOT, expression.operator.line)
        elif token_type == TokenType.GREATER_EQUAL:
            self._emit(OpCode.LESS, expression.operator.line)
            self._emit(OpCode.NOT, expression.operator.line)
        elif token_type == TokenType.LESS_EQUAL:
            self._emit(OpCode.GREATER, expression.operator.line)
            self._emit(OpCode.NOT, expression.operator.line)

    def _logical(self, expression: ast.Logical) -> None:
        self._expression(expression.left)
        if expression.operator.type == TokenType.OR:
            false_jump = self._emit_jump(OpCode.JUMP_IF_FALSE, expression.operator.line)
            end_jump = self._emit_jump(OpCode.JUMP, expression.operator.line)
            self._patch_jump(false_jump)
            self._emit(OpCode.POP, expression.operator.line)
            self._expression(expression.right)
            self._patch_jump(end_jump)
        else:
            end_jump = self._emit_jump(OpCode.JUMP_IF_FALSE, expression.operator.line)
            self._emit(OpCode.POP, expression.operator.line)
            self._expression(expression.right)
            self._patch_jump(end_jump)

    def _let(self, statement: ast.Let) -> None:
        if self.scope_depth > 0:
            self._declare_local(statement.name)
            self._expression(statement.initializer)
            self.locals[-1].depth = self.scope_depth
        else:
            self._expression(statement.initializer)
            name = self._identifier_constant(statement.name)
            self._emit(OpCode.DEFINE_GLOBAL, statement.name.line, name)

    def _if(self, statement: ast.If) -> None:
        self._expression(statement.condition)
        then_jump = self._emit_jump(OpCode.JUMP_IF_FALSE, statement.line)
        self._emit(OpCode.POP, statement.line)
        self._statement(statement.then_branch)
        else_jump = self._emit_jump(OpCode.JUMP, statement.line)
        self._patch_jump(then_jump)
        self._emit(OpCode.POP, statement.line)
        if statement.else_branch is not None:
            self._statement(statement.else_branch)
        self._patch_jump(else_jump)

    def _while(self, statement: ast.While) -> None:
        loop_start = len(self.chunk.code)
        self._expression(statement.condition)
        exit_jump = self._emit_jump(OpCode.JUMP_IF_FALSE, statement.line)
        self._emit(OpCode.POP, statement.line)
        self._statement(statement.body)
        self._emit(OpCode.LOOP, statement.line, loop_start)
        self._patch_jump(exit_jump)
        self._emit(OpCode.POP, statement.line)

    def _function_declaration(self, statement: ast.Function) -> None:
        is_local = self.scope_depth > 0
        if is_local:
            self._declare_local(statement.name)
        child = Compiler(statement.name.lexeme, FunctionType.FUNCTION)
        child.function.arity = len(statement.params)
        child._begin_scope()
        for param in statement.params:
            child._declare_local(param)
            child.locals[-1].depth = child.scope_depth
        for body_statement in statement.body:
            child._statement(body_statement)
        child._emit_return(statement.name.line)
        self._emit_constant(child.function, statement.name.line)
        if is_local:
            self.locals[-1].depth = self.scope_depth
        else:
            name = self._identifier_constant(statement.name)
            self._emit(OpCode.DEFINE_GLOBAL, statement.name.line, name)

    def _return(self, statement: ast.Return) -> None:
        if self.function_type == FunctionType.SCRIPT:
            raise CompileError(f"[line {statement.keyword.line}] Cannot return from top-level code.")
        if statement.value is None:
            self._emit(OpCode.NULL, statement.keyword.line)
        else:
            self._expression(statement.value)
        self._emit(OpCode.RETURN, statement.keyword.line)

    def _named_variable(self, name: Token, assign: bool) -> None:
        local = self._resolve_local(name)
        if local is not None:
            op = OpCode.SET_LOCAL if assign else OpCode.GET_LOCAL
            self._emit(op, name.line, local)
        else:
            index = self._identifier_constant(name)
            op = OpCode.SET_GLOBAL if assign else OpCode.GET_GLOBAL
            self._emit(op, name.line, index)

    def _declare_local(self, name: Token) -> None:
        if len(self.locals) >= 256:
            raise CompileError(f"[line {name.line}] Too many local variables in function.")
        for local in reversed(self.locals):
            if local.depth != -1 and local.depth < self.scope_depth:
                break
            if local.name == name.lexeme:
                raise CompileError(f"[line {name.line}] Variable {name.lexeme!r} already exists in this scope.")
        self.locals.append(Local(name.lexeme, -1))

    def _resolve_local(self, name: Token) -> int | None:
        for index in range(len(self.locals) - 1, -1, -1):
            local = self.locals[index]
            if local.name == name.lexeme:
                if local.depth == -1:
                    raise CompileError(f"[line {name.line}] Cannot read local variable in its own initializer.")
                return index
        return None

    def _begin_scope(self) -> None:
        self.scope_depth += 1

    def _end_scope(self, line: int) -> None:
        self.scope_depth -= 1
        while len(self.locals) > 1 and self.locals[-1].depth > self.scope_depth:
            self._emit(OpCode.POP, line)
            self.locals.pop()

    def _identifier_constant(self, name: Token) -> int:
        return self.chunk.add_constant(name.lexeme)

    def _emit(self, op: OpCode, line: int, arg: int | None = None) -> int:
        return self.chunk.emit(op, line, arg)

    def _emit_constant(self, value, line: int) -> None:
        self._emit(OpCode.CONSTANT, line, self.chunk.add_constant(value))

    def _emit_jump(self, op: OpCode, line: int) -> int:
        return self._emit(op, line, 0)

    def _patch_jump(self, instruction: int) -> None:
        self.chunk.patch(instruction, len(self.chunk.code))

    def _emit_return(self, line: int) -> None:
        self._emit(OpCode.NULL, line)
        self._emit(OpCode.RETURN, line)

    @staticmethod
    def _expr_line(expression: ast.Expr) -> int:
        if isinstance(expression, ast.Literal):
            return expression.line
        if isinstance(expression, (ast.Unary, ast.Binary, ast.Logical)):
            return expression.operator.line
        if isinstance(expression, (ast.Variable, ast.Assign)):
            return expression.name.line
        if isinstance(expression, ast.Call):
            return expression.paren.line
        if isinstance(expression, ast.Grouping):
            return Compiler._expr_line(expression.expression)
        return 1

    @staticmethod
    def _last_line(statements: list[ast.Stmt]) -> int:
        if not statements:
            return 1
        statement = statements[-1]
        if isinstance(statement, (ast.Let, ast.Function)):
            return statement.name.line
        if isinstance(statement, ast.Return):
            return statement.keyword.line
        if isinstance(statement, (ast.Print, ast.If, ast.While)):
            return statement.line
        if isinstance(statement, ast.Expression):
            return Compiler._expr_line(statement.expression)
        if isinstance(statement, ast.Block):
            return Compiler._last_line(statement.statements)
        return 1


def compile_source(source: str, name: str = "<script>") -> FunctionObject:
    tokens = Lexer(source).scan_tokens()
    statements = Parser(tokens).parse()
    return Compiler(name).compile(statements)

