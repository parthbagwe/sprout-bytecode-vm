from dataclasses import dataclass
from typing import Callable

from .bytecode import FunctionObject, Instruction, OpCode
from .errors import VMError


@dataclass(slots=True)
class CallFrame:
    function: FunctionObject
    ip: int
    slot_start: int


class VM:
    STACK_MAX = 65_536
    FRAMES_MAX = 256

    def __init__(
        self,
        output: Callable[[str], None] = print,
        trace: bool = False,
        trace_output: Callable[[str], None] | None = None,
        instruction_limit: int | None = None,
    ):
        self.output = output
        self.trace = trace
        self.trace_output = trace_output or output
        self.instruction_limit = instruction_limit
        self.instructions_executed = 0
        self.stack: list[object] = []
        self.frames: list[CallFrame] = []
        self.globals: dict[str, object] = {}

    def interpret(self, function: FunctionObject):
        self.stack.clear()
        self.frames.clear()
        self.instructions_executed = 0
        self.stack.append(function)
        self._call(function, 0)
        return self._run()

    def _run(self):
        while True:
            frame = self.frames[-1]
            if frame.ip >= len(frame.function.chunk.code):
                self._runtime_error("Instruction pointer escaped the bytecode chunk.", None)
            instruction = frame.function.chunk.code[frame.ip]
            frame.ip += 1
            self.instructions_executed += 1
            if self.instruction_limit is not None and self.instructions_executed > self.instruction_limit:
                self._runtime_error(
                    f"Instruction limit of {self.instruction_limit:,} exceeded. Check for an infinite loop.",
                    instruction,
                )
            if self.trace:
                self._trace(frame, instruction)
            op = instruction.op

            if op == OpCode.CONSTANT:
                self._push(frame.function.chunk.constants[instruction.arg])
            elif op == OpCode.NULL:
                self._push(None)
            elif op == OpCode.TRUE:
                self._push(True)
            elif op == OpCode.FALSE:
                self._push(False)
            elif op == OpCode.POP:
                self._pop(instruction)
            elif op == OpCode.GET_LOCAL:
                self._push(self.stack[frame.slot_start + instruction.arg])
            elif op == OpCode.SET_LOCAL:
                self.stack[frame.slot_start + instruction.arg] = self._peek(0, instruction)
            elif op == OpCode.GET_GLOBAL:
                name = self._constant_name(frame, instruction)
                if name not in self.globals:
                    self._runtime_error(f"Undefined variable {name!r}.", instruction)
                self._push(self.globals[name])
            elif op == OpCode.DEFINE_GLOBAL:
                name = self._constant_name(frame, instruction)
                self.globals[name] = self._pop(instruction)
            elif op == OpCode.SET_GLOBAL:
                name = self._constant_name(frame, instruction)
                if name not in self.globals:
                    self._runtime_error(f"Undefined variable {name!r}.", instruction)
                self.globals[name] = self._peek(0, instruction)
            elif op == OpCode.EQUAL:
                right = self._pop(instruction)
                left = self._pop(instruction)
                self._push(left == right)
            elif op in {OpCode.GREATER, OpCode.LESS, OpCode.SUBTRACT, OpCode.MULTIPLY, OpCode.DIVIDE}:
                self._numeric_binary(op, instruction)
            elif op == OpCode.ADD:
                self._add(instruction)
            elif op == OpCode.NOT:
                self._push(self._is_falsey(self._pop(instruction)))
            elif op == OpCode.NEGATE:
                value = self._pop(instruction)
                if not self._is_number(value):
                    self._runtime_error("Operand must be a number.", instruction)
                self._push(-value)
            elif op == OpCode.PRINT:
                self.output(self.stringify(self._pop(instruction)))
            elif op == OpCode.JUMP:
                frame.ip = instruction.arg
            elif op == OpCode.JUMP_IF_FALSE:
                if self._is_falsey(self._peek(0, instruction)):
                    frame.ip = instruction.arg
            elif op == OpCode.LOOP:
                frame.ip = instruction.arg
            elif op == OpCode.CALL:
                callee = self._peek(instruction.arg, instruction)
                if not isinstance(callee, FunctionObject):
                    self._runtime_error("Can only call functions.", instruction)
                self._call(callee, instruction.arg, instruction)
            elif op == OpCode.RETURN:
                result = self._pop(instruction)
                completed = self.frames.pop()
                del self.stack[completed.slot_start:]
                if not self.frames:
                    return result
                self._push(result)
            else:
                self._runtime_error(f"Unknown opcode {op}.", instruction)

    def _call(self, function: FunctionObject, arg_count: int, instruction: Instruction | None = None) -> None:
        if arg_count != function.arity:
            self._runtime_error(
                f"Function {function.name!r} expects {function.arity} arguments but got {arg_count}.",
                instruction,
            )
        if len(self.frames) >= self.FRAMES_MAX:
            self._runtime_error("Call stack overflow.", instruction)
        self.frames.append(CallFrame(function, 0, len(self.stack) - arg_count - 1))

    def _add(self, instruction: Instruction) -> None:
        right = self._pop(instruction)
        left = self._pop(instruction)
        if self._is_number(left) and self._is_number(right):
            self._push(left + right)
        elif isinstance(left, str) and isinstance(right, str):
            self._push(left + right)
        else:
            self._runtime_error("Operands to '+' must be two numbers or two strings.", instruction)

    def _numeric_binary(self, op: OpCode, instruction: Instruction) -> None:
        right = self._pop(instruction)
        left = self._pop(instruction)
        if not self._is_number(left) or not self._is_number(right):
            self._runtime_error("Operands must be numbers.", instruction)
        if op == OpCode.GREATER:
            self._push(left > right)
        elif op == OpCode.LESS:
            self._push(left < right)
        elif op == OpCode.SUBTRACT:
            self._push(left - right)
        elif op == OpCode.MULTIPLY:
            self._push(left * right)
        elif op == OpCode.DIVIDE:
            if right == 0:
                self._runtime_error("Division by zero.", instruction)
            self._push(left / right)

    def _push(self, value) -> None:
        if len(self.stack) >= self.STACK_MAX:
            self._runtime_error("Value stack overflow.", None)
        self.stack.append(value)

    def _pop(self, instruction: Instruction | None):
        if not self.stack:
            self._runtime_error("Value stack underflow.", instruction)
        return self.stack.pop()

    def _peek(self, distance: int, instruction: Instruction | None):
        if distance >= len(self.stack):
            self._runtime_error("Value stack underflow.", instruction)
        return self.stack[-1 - distance]

    @staticmethod
    def _is_falsey(value) -> bool:
        return value is None or value is False

    @staticmethod
    def _is_number(value) -> bool:
        return isinstance(value, float) and not isinstance(value, bool)

    @staticmethod
    def stringify(value) -> str:
        if value is None:
            return "null"
        if value is True:
            return "true"
        if value is False:
            return "false"
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    @staticmethod
    def _constant_name(frame: CallFrame, instruction: Instruction) -> str:
        value = frame.function.chunk.constants[instruction.arg]
        if not isinstance(value, str):
            raise VMError("Invalid bytecode: global name is not a string.")
        return value

    def _trace(self, frame: CallFrame, instruction: Instruction) -> None:
        stack = " ".join(f"[{self.stringify(value)}]" for value in self.stack)
        arg = "" if instruction.arg is None else f" {instruction.arg}"
        self.trace_output(f"          {stack}")
        self.trace_output(f"{frame.ip - 1:04d} L{instruction.line:<3} {instruction.op.name}{arg}")

    def _runtime_error(self, message: str, instruction: Instruction | None) -> None:
        trace: list[str] = []
        for index, frame in enumerate(reversed(self.frames)):
            if index == 0 and instruction is not None:
                line = instruction.line
            elif frame.ip:
                line = frame.function.chunk.code[frame.ip - 1].line
            else:
                line = 1
            trace.append(f"  [line {line}] in {frame.function.name}()")
        details = "\n".join(trace)
        raise VMError(f"{message}\n{details}" if details else message)
