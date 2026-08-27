from __future__ import annotations

import io
import struct
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, BinaryIO

from .errors import BytecodeError


MAGIC = b"SPROUTBC"
FORMAT_VERSION = 1


class OpCode(IntEnum):
    CONSTANT = 1
    NULL = 2
    TRUE = 3
    FALSE = 4
    POP = 5
    GET_LOCAL = 6
    SET_LOCAL = 7
    GET_GLOBAL = 8
    DEFINE_GLOBAL = 9
    SET_GLOBAL = 10
    EQUAL = 11
    GREATER = 12
    LESS = 13
    ADD = 14
    SUBTRACT = 15
    MULTIPLY = 16
    DIVIDE = 17
    NOT = 18
    NEGATE = 19
    PRINT = 20
    JUMP = 21
    JUMP_IF_FALSE = 22
    LOOP = 23
    CALL = 24
    RETURN = 25


OPERAND_OPS = {
    OpCode.CONSTANT,
    OpCode.GET_LOCAL,
    OpCode.SET_LOCAL,
    OpCode.GET_GLOBAL,
    OpCode.DEFINE_GLOBAL,
    OpCode.SET_GLOBAL,
    OpCode.JUMP,
    OpCode.JUMP_IF_FALSE,
    OpCode.LOOP,
    OpCode.CALL,
}


@dataclass(slots=True)
class Instruction:
    op: OpCode
    arg: int | None
    line: int


@dataclass(slots=True)
class Chunk:
    code: list[Instruction] = field(default_factory=list)
    constants: list[Any] = field(default_factory=list)

    def emit(self, op: OpCode, line: int, arg: int | None = None) -> int:
        if (op in OPERAND_OPS) != (arg is not None):
            raise BytecodeError(f"Invalid operand for {op.name}.")
        self.code.append(Instruction(op, arg, line))
        return len(self.code) - 1

    def add_constant(self, value: Any) -> int:
        if len(self.constants) >= 2**32:
            raise BytecodeError("Too many constants in one chunk.")
        self.constants.append(value)
        return len(self.constants) - 1

    def patch(self, instruction: int, target: int) -> None:
        self.code[instruction].arg = target


@dataclass(slots=True)
class FunctionObject:
    name: str
    arity: int = 0
    chunk: Chunk = field(default_factory=Chunk)

    def __repr__(self) -> str:
        return f"<fn {self.name}>"


def disassemble(function: FunctionObject, recursive: bool = True) -> str:
    sections: list[str] = []

    def visit(fn: FunctionObject) -> None:
        lines = [f"== {fn.name} (arity {fn.arity}) =="]
        for offset, instruction in enumerate(fn.chunk.code):
            operand = ""
            if instruction.arg is not None:
                operand = f" {instruction.arg:04d}"
                if instruction.op in {
                    OpCode.CONSTANT,
                    OpCode.GET_GLOBAL,
                    OpCode.DEFINE_GLOBAL,
                    OpCode.SET_GLOBAL,
                }:
                    value = fn.chunk.constants[instruction.arg]
                    operand += f" {value!r}"
            lines.append(f"{offset:04d}  {instruction.line:4d}  {instruction.op.name:<18}{operand}")
        sections.append("\n".join(lines))
        if recursive:
            for constant in fn.chunk.constants:
                if isinstance(constant, FunctionObject):
                    visit(constant)

    visit(function)
    return "\n\n".join(sections)


def write_bytecode(function: FunctionObject, path: str | Path) -> None:
    with Path(path).open("wb") as stream:
        stream.write(MAGIC)
        stream.write(bytes([FORMAT_VERSION]))
        _write_function(stream, function)


def read_bytecode(path: str | Path) -> FunctionObject:
    try:
        data = Path(path).read_bytes()
        stream = io.BytesIO(data)
        if stream.read(len(MAGIC)) != MAGIC:
            raise BytecodeError("Not a Sprout bytecode file (bad magic header).")
        version = _read_exact(stream, 1)[0]
        if version != FORMAT_VERSION:
            raise BytecodeError(f"Unsupported bytecode version {version}.")
        function = _read_function(stream)
        if stream.read(1):
            raise BytecodeError("Unexpected data at end of bytecode file.")
        return function
    except OSError as error:
        raise BytecodeError(str(error)) from error
    except (struct.error, UnicodeDecodeError, IndexError, ValueError) as error:
        raise BytecodeError(f"Malformed bytecode: {error}") from error


def _write_function(stream: BinaryIO, function: FunctionObject) -> None:
    _write_string(stream, function.name)
    stream.write(struct.pack("<B", function.arity))
    stream.write(struct.pack("<I", len(function.chunk.constants)))
    for constant in function.chunk.constants:
        _write_constant(stream, constant)
    stream.write(struct.pack("<I", len(function.chunk.code)))
    for instruction in function.chunk.code:
        stream.write(struct.pack("<B", instruction.op.value))
        if instruction.op in OPERAND_OPS:
            stream.write(struct.pack("<I", instruction.arg))
        stream.write(struct.pack("<I", instruction.line))


def _read_function(stream: BinaryIO) -> FunctionObject:
    name = _read_string(stream)
    arity = struct.unpack("<B", _read_exact(stream, 1))[0]
    function = FunctionObject(name, arity)
    constant_count = struct.unpack("<I", _read_exact(stream, 4))[0]
    for _ in range(constant_count):
        function.chunk.constants.append(_read_constant(stream))
    instruction_count = struct.unpack("<I", _read_exact(stream, 4))[0]
    for _ in range(instruction_count):
        op = OpCode(struct.unpack("<B", _read_exact(stream, 1))[0])
        arg = struct.unpack("<I", _read_exact(stream, 4))[0] if op in OPERAND_OPS else None
        line = struct.unpack("<I", _read_exact(stream, 4))[0]
        function.chunk.code.append(Instruction(op, arg, line))
    _validate(function)
    return function


def _write_constant(stream: BinaryIO, value: Any) -> None:
    if value is None:
        stream.write(b"\x00")
    elif value is False:
        stream.write(b"\x01")
    elif value is True:
        stream.write(b"\x02")
    elif isinstance(value, float):
        stream.write(b"\x03" + struct.pack("<d", value))
    elif isinstance(value, str):
        stream.write(b"\x04")
        _write_string(stream, value)
    elif isinstance(value, FunctionObject):
        stream.write(b"\x05")
        _write_function(stream, value)
    else:
        raise BytecodeError(f"Cannot encode constant {value!r}.")


def _read_constant(stream: BinaryIO) -> Any:
    tag = _read_exact(stream, 1)[0]
    if tag == 0:
        return None
    if tag == 1:
        return False
    if tag == 2:
        return True
    if tag == 3:
        return struct.unpack("<d", _read_exact(stream, 8))[0]
    if tag == 4:
        return _read_string(stream)
    if tag == 5:
        return _read_function(stream)
    raise BytecodeError(f"Unknown constant tag {tag}.")


def _write_string(stream: BinaryIO, value: str) -> None:
    encoded = value.encode("utf-8")
    stream.write(struct.pack("<I", len(encoded)))
    stream.write(encoded)


def _read_string(stream: BinaryIO) -> str:
    length = struct.unpack("<I", _read_exact(stream, 4))[0]
    return _read_exact(stream, length).decode("utf-8")


def _read_exact(stream: BinaryIO, length: int) -> bytes:
    data = stream.read(length)
    if len(data) != length:
        raise BytecodeError("Unexpected end of bytecode file.")
    return data


def _validate(function: FunctionObject) -> None:
    code_length = len(function.chunk.code)
    constants_length = len(function.chunk.constants)
    constant_ops = {
        OpCode.CONSTANT,
        OpCode.GET_GLOBAL,
        OpCode.DEFINE_GLOBAL,
        OpCode.SET_GLOBAL,
    }
    for instruction in function.chunk.code:
        if instruction.op in constant_ops and instruction.arg >= constants_length:
            raise BytecodeError(f"Constant index {instruction.arg} is out of range.")
        if instruction.op in {OpCode.JUMP, OpCode.JUMP_IF_FALSE, OpCode.LOOP}:
            if instruction.arg >= code_length:
                raise BytecodeError(f"Jump target {instruction.arg} is out of range.")
    for constant in function.chunk.constants:
        if isinstance(constant, FunctionObject):
            _validate(constant)

