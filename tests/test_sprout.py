import tempfile
import unittest
from pathlib import Path

from sprout.bytecode import MAGIC, disassemble, read_bytecode, write_bytecode
from sprout.compiler import compile_source
from sprout.errors import CompileError, VMError
from sprout.vm import VM
from sprout.web_server import run_playground


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

    def test_playground_returns_output_bytecode_and_stats(self):
        result = run_playground("fn twice(x) { return x * 2; } print twice(6);", trace=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["output"], "12")
        self.assertIn("CALL", result["bytecode"])
        self.assertIn("MULTIPLY", result["trace"])
        self.assertGreater(result["stats"]["executedInstructions"], 0)

    def test_playground_stops_infinite_loop(self):
        result = run_playground("while true {}", instruction_limit=50)
        self.assertFalse(result["ok"])
        self.assertIn("Instruction limit", result["error"])

    def test_playground_caps_large_trace(self):
        result = run_playground("let i = 0; while i < 1000 { i = i + 1; }", trace=True)
        self.assertTrue(result["ok"])
        self.assertIn("trace truncated", result["trace"])


if __name__ == "__main__":
    unittest.main()
