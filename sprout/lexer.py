from .errors import LexError
from .tokens import KEYWORDS, Token, TokenType


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.tokens: list[Token] = []
        self.start = 0
        self.current = 0
        self.line = 1
        self.column = 1
        self.start_column = 1

    def scan_tokens(self) -> list[Token]:
        while not self._at_end():
            self.start = self.current
            self.start_column = self.column
            self._scan_token()
        self.tokens.append(Token(TokenType.EOF, "", None, self.line, self.column))
        return self.tokens

    def _scan_token(self) -> None:
        c = self._advance()
        single = {
            "(": TokenType.LEFT_PAREN,
            ")": TokenType.RIGHT_PAREN,
            "{": TokenType.LEFT_BRACE,
            "}": TokenType.RIGHT_BRACE,
            ",": TokenType.COMMA,
            "-": TokenType.MINUS,
            "+": TokenType.PLUS,
            ";": TokenType.SEMICOLON,
            "*": TokenType.STAR,
        }
        if c in single:
            self._add(single[c])
        elif c == "!":
            self._add(TokenType.BANG_EQUAL if self._match("=") else TokenType.BANG)
        elif c == "=":
            self._add(TokenType.EQUAL_EQUAL if self._match("=") else TokenType.EQUAL)
        elif c == "<":
            self._add(TokenType.LESS_EQUAL if self._match("=") else TokenType.LESS)
        elif c == ">":
            self._add(TokenType.GREATER_EQUAL if self._match("=") else TokenType.GREATER)
        elif c == "/":
            if self._match("/"):
                while self._peek() != "\n" and not self._at_end():
                    self._advance()
            else:
                self._add(TokenType.SLASH)
        elif c in " \r\t":
            pass
        elif c == "\n":
            self.line += 1
            self.column = 1
        elif c == '"':
            self._string()
        elif c.isdigit():
            self._number()
        elif c.isalpha() or c == "_":
            self._identifier()
        else:
            raise LexError(f"[line {self.line}:{self.start_column}] Unexpected character {c!r}.")

    def _string(self) -> None:
        value: list[str] = []
        escapes = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
        while not self._at_end() and self._peek() != '"':
            c = self._advance()
            if c == "\n":
                self.line += 1
                self.column = 1
                value.append("\n")
            elif c == "\\" and not self._at_end():
                escaped = self._advance()
                if escaped not in escapes:
                    raise LexError(f"[line {self.line}:{self.column - 1}] Unknown escape \\{escaped}.")
                value.append(escapes[escaped])
            else:
                value.append(c)
        if self._at_end():
            raise LexError(f"[line {self.line}] Unterminated string.")
        self._advance()
        self._add(TokenType.STRING, "".join(value))

    def _number(self) -> None:
        while self._peek().isdigit():
            self._advance()
        if self._peek() == "." and self._peek_next().isdigit():
            self._advance()
            while self._peek().isdigit():
                self._advance()
        self._add(TokenType.NUMBER, float(self.source[self.start:self.current]))

    def _identifier(self) -> None:
        while self._peek().isalnum() or self._peek() == "_":
            self._advance()
        text = self.source[self.start:self.current]
        self._add(KEYWORDS.get(text, TokenType.IDENTIFIER))

    def _at_end(self) -> bool:
        return self.current >= len(self.source)

    def _advance(self) -> str:
        c = self.source[self.current]
        self.current += 1
        self.column += 1
        return c

    def _match(self, expected: str) -> bool:
        if self._at_end() or self.source[self.current] != expected:
            return False
        self.current += 1
        self.column += 1
        return True

    def _peek(self) -> str:
        return "\0" if self._at_end() else self.source[self.current]

    def _peek_next(self) -> str:
        return "\0" if self.current + 1 >= len(self.source) else self.source[self.current + 1]

    def _add(self, token_type: TokenType, literal=None) -> None:
        text = self.source[self.start:self.current]
        self.tokens.append(Token(token_type, text, literal, self.line, self.start_column))

