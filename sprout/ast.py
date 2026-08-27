from dataclasses import dataclass
from typing import Any

from .tokens import Token


class Expr:
    pass


class Stmt:
    pass


@dataclass(slots=True)
class Literal(Expr):
    value: Any
    line: int


@dataclass(slots=True)
class Grouping(Expr):
    expression: Expr


@dataclass(slots=True)
class Unary(Expr):
    operator: Token
    right: Expr


@dataclass(slots=True)
class Binary(Expr):
    left: Expr
    operator: Token
    right: Expr


@dataclass(slots=True)
class Logical(Expr):
    left: Expr
    operator: Token
    right: Expr


@dataclass(slots=True)
class Variable(Expr):
    name: Token


@dataclass(slots=True)
class Assign(Expr):
    name: Token
    value: Expr


@dataclass(slots=True)
class Call(Expr):
    callee: Expr
    paren: Token
    arguments: list[Expr]


@dataclass(slots=True)
class Expression(Stmt):
    expression: Expr


@dataclass(slots=True)
class Print(Stmt):
    expression: Expr
    line: int


@dataclass(slots=True)
class Let(Stmt):
    name: Token
    initializer: Expr


@dataclass(slots=True)
class Block(Stmt):
    statements: list[Stmt]


@dataclass(slots=True)
class If(Stmt):
    condition: Expr
    then_branch: Stmt
    else_branch: Stmt | None
    line: int


@dataclass(slots=True)
class While(Stmt):
    condition: Expr
    body: Stmt
    line: int


@dataclass(slots=True)
class Function(Stmt):
    name: Token
    params: list[Token]
    body: list[Stmt]


@dataclass(slots=True)
class Return(Stmt):
    keyword: Token
    value: Expr | None

