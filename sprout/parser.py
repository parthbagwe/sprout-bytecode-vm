from . import ast
from .errors import ParseError
from .tokens import Token, TokenType


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.current = 0

    def parse(self) -> list[ast.Stmt]:
        statements: list[ast.Stmt] = []
        while not self._at_end():
            statements.append(self._declaration())
        return statements

    def _declaration(self) -> ast.Stmt:
        if self._match(TokenType.FN):
            return self._function()
        if self._match(TokenType.LET):
            return self._let_declaration()
        return self._statement()

    def _function(self) -> ast.Function:
        name = self._consume(TokenType.IDENTIFIER, "Expected function name.")
        self._consume(TokenType.LEFT_PAREN, "Expected '(' after function name.")
        params: list[Token] = []
        if not self._check(TokenType.RIGHT_PAREN):
            while True:
                if len(params) >= 255:
                    raise self._error(self._peek(), "A function cannot have more than 255 parameters.")
                params.append(self._consume(TokenType.IDENTIFIER, "Expected parameter name."))
                if not self._match(TokenType.COMMA):
                    break
        self._consume(TokenType.RIGHT_PAREN, "Expected ')' after parameters.")
        self._consume(TokenType.LEFT_BRACE, "Expected '{' before function body.")
        return ast.Function(name, params, self._block())

    def _let_declaration(self) -> ast.Let:
        name = self._consume(TokenType.IDENTIFIER, "Expected variable name.")
        initializer: ast.Expr = ast.Literal(None, name.line)
        if self._match(TokenType.EQUAL):
            initializer = self._expression()
        self._consume(TokenType.SEMICOLON, "Expected ';' after variable declaration.")
        return ast.Let(name, initializer)

    def _statement(self) -> ast.Stmt:
        if self._match(TokenType.PRINT):
            return self._print_statement()
        if self._match(TokenType.RETURN):
            return self._return_statement()
        if self._match(TokenType.IF):
            return self._if_statement()
        if self._match(TokenType.WHILE):
            return self._while_statement()
        if self._match(TokenType.LEFT_BRACE):
            return ast.Block(self._block())
        return self._expression_statement()

    def _print_statement(self) -> ast.Print:
        keyword = self._previous()
        value = self._expression()
        self._consume(TokenType.SEMICOLON, "Expected ';' after value.")
        return ast.Print(value, keyword.line)

    def _return_statement(self) -> ast.Return:
        keyword = self._previous()
        value = None if self._check(TokenType.SEMICOLON) else self._expression()
        self._consume(TokenType.SEMICOLON, "Expected ';' after return value.")
        return ast.Return(keyword, value)

    def _if_statement(self) -> ast.If:
        keyword = self._previous()
        condition = self._expression()
        self._consume(TokenType.LEFT_BRACE, "Expected '{' after if condition.")
        then_branch: ast.Stmt = ast.Block(self._block())
        else_branch = None
        if self._match(TokenType.ELSE):
            if self._match(TokenType.IF):
                else_branch = self._if_statement()
            else:
                self._consume(TokenType.LEFT_BRACE, "Expected '{' after else.")
                else_branch = ast.Block(self._block())
        return ast.If(condition, then_branch, else_branch, keyword.line)

    def _while_statement(self) -> ast.While:
        keyword = self._previous()
        condition = self._expression()
        self._consume(TokenType.LEFT_BRACE, "Expected '{' after while condition.")
        return ast.While(condition, ast.Block(self._block()), keyword.line)

    def _block(self) -> list[ast.Stmt]:
        statements: list[ast.Stmt] = []
        while not self._check(TokenType.RIGHT_BRACE) and not self._at_end():
            statements.append(self._declaration())
        self._consume(TokenType.RIGHT_BRACE, "Expected '}' after block.")
        return statements

    def _expression_statement(self) -> ast.Expression:
        expression = self._expression()
        self._consume(TokenType.SEMICOLON, "Expected ';' after expression.")
        return ast.Expression(expression)

    def _expression(self) -> ast.Expr:
        return self._assignment()

    def _assignment(self) -> ast.Expr:
        expression = self._or()
        if self._match(TokenType.EQUAL):
            equals = self._previous()
            value = self._assignment()
            if isinstance(expression, ast.Variable):
                return ast.Assign(expression.name, value)
            raise self._error(equals, "Invalid assignment target.")
        return expression

    def _or(self) -> ast.Expr:
        expression = self._and()
        while self._match(TokenType.OR):
            operator = self._previous()
            expression = ast.Logical(expression, operator, self._and())
        return expression

    def _and(self) -> ast.Expr:
        expression = self._equality()
        while self._match(TokenType.AND):
            operator = self._previous()
            expression = ast.Logical(expression, operator, self._equality())
        return expression

    def _equality(self) -> ast.Expr:
        expression = self._comparison()
        while self._match(TokenType.BANG_EQUAL, TokenType.EQUAL_EQUAL):
            operator = self._previous()
            expression = ast.Binary(expression, operator, self._comparison())
        return expression

    def _comparison(self) -> ast.Expr:
        expression = self._term()
        while self._match(TokenType.GREATER, TokenType.GREATER_EQUAL, TokenType.LESS, TokenType.LESS_EQUAL):
            operator = self._previous()
            expression = ast.Binary(expression, operator, self._term())
        return expression

    def _term(self) -> ast.Expr:
        expression = self._factor()
        while self._match(TokenType.MINUS, TokenType.PLUS):
            operator = self._previous()
            expression = ast.Binary(expression, operator, self._factor())
        return expression

    def _factor(self) -> ast.Expr:
        expression = self._unary()
        while self._match(TokenType.SLASH, TokenType.STAR):
            operator = self._previous()
            expression = ast.Binary(expression, operator, self._unary())
        return expression

    def _unary(self) -> ast.Expr:
        if self._match(TokenType.BANG, TokenType.MINUS):
            operator = self._previous()
            return ast.Unary(operator, self._unary())
        return self._call()

    def _call(self) -> ast.Expr:
        expression = self._primary()
        while self._match(TokenType.LEFT_PAREN):
            arguments: list[ast.Expr] = []
            if not self._check(TokenType.RIGHT_PAREN):
                while True:
                    if len(arguments) >= 255:
                        raise self._error(self._peek(), "A call cannot have more than 255 arguments.")
                    arguments.append(self._expression())
                    if not self._match(TokenType.COMMA):
                        break
            paren = self._consume(TokenType.RIGHT_PAREN, "Expected ')' after arguments.")
            expression = ast.Call(expression, paren, arguments)
        return expression

    def _primary(self) -> ast.Expr:
        if self._match(TokenType.FALSE):
            return ast.Literal(False, self._previous().line)
        if self._match(TokenType.TRUE):
            return ast.Literal(True, self._previous().line)
        if self._match(TokenType.NULL):
            return ast.Literal(None, self._previous().line)
        if self._match(TokenType.NUMBER, TokenType.STRING):
            token = self._previous()
            return ast.Literal(token.literal, token.line)
        if self._match(TokenType.IDENTIFIER):
            return ast.Variable(self._previous())
        if self._match(TokenType.LEFT_PAREN):
            expression = self._expression()
            self._consume(TokenType.RIGHT_PAREN, "Expected ')' after expression.")
            return ast.Grouping(expression)
        raise self._error(self._peek(), "Expected expression.")

    def _match(self, *types: TokenType) -> bool:
        for token_type in types:
            if self._check(token_type):
                self._advance()
                return True
        return False

    def _consume(self, token_type: TokenType, message: str) -> Token:
        if self._check(token_type):
            return self._advance()
        raise self._error(self._peek(), message)

    def _check(self, token_type: TokenType) -> bool:
        return self._peek().type == token_type

    def _advance(self) -> Token:
        if not self._at_end():
            self.current += 1
        return self._previous()

    def _at_end(self) -> bool:
        return self._peek().type == TokenType.EOF

    def _peek(self) -> Token:
        return self.tokens[self.current]

    def _previous(self) -> Token:
        return self.tokens[self.current - 1]

    @staticmethod
    def _error(token: Token, message: str) -> ParseError:
        where = "at end" if token.type == TokenType.EOF else f"at {token.lexeme!r}"
        return ParseError(f"[line {token.line}:{token.column}] Error {where}: {message}")

