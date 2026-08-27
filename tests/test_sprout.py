import tempfile
import unittest
from pathlib import Path

from sprout.bytecode import MAGIC, disassemble, read_bytecode, write_bytecode
from sprout.compiler import compile_source
from sprout.errors import CompileError, VMError
from sprout.vm import VM


def run(source: str) -> list[str]:
    output: list[str] = []
    VM(output.append).interpret(compile_source(source))
    return output


class SproutTests(unittest.TestCase):
    def test_precedence_and_strings(self):
        self.assertEqual(run('print 2 + 3 * 4; print "hello, " + "vm";'), ["14", "hello, vm"])

    def test_locals_and_shadowing(self):
        source = """
        let value = 1;
        {
          let value = 2;
          print value;
        }
        print value;
        """
        self.assertEqual(run(source), ["2", "1"])

    def test_while_and_assignment(self):
        source = """
        let i = 0;
        let sum = 0;
        while i < 5 {
          sum = sum + i;
          i = i + 1;
        }
        print sum;
        """
        self.assertEqual(run(source), ["10"])

    def test_recursive_function(self):
        source = """
        fn fib(n) {
          if n < 2 { return n; }
          return fib(n - 1) + fib(n - 2);
        }
        print fib(10);
        """
        self.assertEqual(run(source), ["55"])

    def test_short_circuit(self):
        self.assertEqual(run("print false and missing; print true or missing;"), ["false", "true"])

    def test_binary_bytecode_round_trip(self):
        function = compile_source("fn twice(x) { return x * 2; } print twice(9);")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.sbc"
            write_bytecode(function, path)
            self.assertTrue(path.read_bytes().startswith(MAGIC))
            output: list[str] = []
            VM(output.append).interpret(read_bytecode(path))
        self.assertEqual(output, ["18"])

    def test_disassembler_contains_opcodes(self):
        listing = disassemble(compile_source("print 1 + 2;"))
        self.assertIn("CONSTANT", listing)
        self.assertIn("ADD", listing)
        self.assertIn("PRINT", listing)

    def test_top_level_return_is_compile_error(self):
        with self.assertRaises(CompileError):
            compile_source("return 1;")

    def test_runtime_error_has_source_trace(self):
        with self.assertRaisesRegex(VMError, r"(?s)Division by zero.*line 1"):
            run("print 1 / 0;")


if __name__ == "__main__":
    unittest.main()
