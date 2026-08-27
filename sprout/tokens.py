from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class TokenType(Enum):
    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()
    LEFT_BRACE = auto()
    RIGHT_BRACE = auto()
    COMMA = auto()
    MINUS = auto()
    PLUS = auto()
    SEMICOLON = auto()
    SLASH = auto()
    STAR = auto()

    BANG = auto()
    BANG_EQUAL = auto()
    EQUAL = auto()
    EQUAL_EQUAL = auto()
    GREATER = auto()
    GREATER_EQUAL = auto()
    LESS = auto()
    LESS_EQUAL = auto()

    IDENTIFIER = auto()
    STRING = auto()
    NUMBER = auto()

    AND = auto()
    ELSE = auto()
    FALSE = auto()
    FN = auto()
    IF = auto()
    LET = auto()
    NULL = auto()
    OR = auto()
    PRINT = auto()
    RETURN = auto()
    TRUE = auto()
    WHILE = auto()
    EOF = auto()


KEYWORDS = {
    "and": TokenType.AND,
    "else": TokenType.ELSE,
    "false": TokenType.FALSE,
    "fn": TokenType.FN,
    "if": TokenType.IF,
    "let": TokenType.LET,
    "null": TokenType.NULL,
    "or": TokenType.OR,
    "print": TokenType.PRINT,
    "return": TokenType.RETURN,
    "true": TokenType.TRUE,
    "while": TokenType.WHILE,
}


@dataclass(frozen=True, slots=True)
class Token:
    type: TokenType
    lexeme: str
    literal: Any
    line: int
    column: int

