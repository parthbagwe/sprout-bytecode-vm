class SproutError(Exception):
    """Base class for user-facing Sprout errors."""


class LexError(SproutError):
    pass


class ParseError(SproutError):
    pass


class CompileError(SproutError):
    pass


class BytecodeError(SproutError):
    pass


class VMError(SproutError):
    pass

