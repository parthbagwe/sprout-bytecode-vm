import argparse
import sys
from pathlib import Path

from .bytecode import disassemble, read_bytecode, write_bytecode
from .compiler import compile_source
from .errors import SproutError
from .vm import VM


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sprout",
        description="Compile Sprout programs to custom bytecode and run them on a stack VM.",
    )
    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="Compile and run a .sprout source file.")
    run.add_argument("file", type=Path)
    run.add_argument("--trace", action="store_true", help="Trace each VM instruction and stack state.")

    compile_command = subparsers.add_parser("compile", help="Compile source to a binary .sbc file.")
    compile_command.add_argument("file", type=Path)
    compile_command.add_argument("-o", "--output", type=Path)

    execute = subparsers.add_parser("exec", help="Execute a compiled .sbc file.")
    execute.add_argument("file", type=Path)
    execute.add_argument("--trace", action="store_true")

    dis = subparsers.add_parser("dis", help="Disassemble a .sprout or .sbc file.")
    dis.add_argument("file", type=Path)

    web = subparsers.add_parser("web", help="Run the browser playground on localhost.")
    web.add_argument("--host", default="127.0.0.1", help="Address to bind (default: 127.0.0.1).")
    web.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000).")

    subparsers.add_parser("repl", help="Start an interactive Sprout prompt.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            function = _compile_file(args.file)
            VM(trace=args.trace).interpret(function)
        elif args.command == "compile":
            function = _compile_file(args.file)
            output = args.output or args.file.with_suffix(".sbc")
            write_bytecode(function, output)
            print(f"Wrote {output}")
        elif args.command == "exec":
            VM(trace=args.trace).interpret(read_bytecode(args.file))
        elif args.command == "dis":
            function = read_bytecode(args.file) if args.file.suffix == ".sbc" else _compile_file(args.file)
            print(disassemble(function))
        elif args.command == "web":
            from .web_server import serve

            serve(args.host, args.port)
        elif args.command == "repl" or args.command is None:
            _repl()
        else:
            parser.print_help()
            return 2
        return 0
    except (SproutError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _compile_file(path: Path):
    source = path.read_text(encoding="utf-8")
    return compile_source(source, path.name)


def _repl() -> None:
    vm = VM()
    print("Sprout 0.1 — enter a statement, or Ctrl+Z/Ctrl+D to exit")
    while True:
        try:
            line = input("> ")
        except EOFError:
            print()
            break
        if not line.strip():
            continue
        try:
            vm.interpret(compile_source(line, "<repl>"))
        except SproutError as error:
            print(f"error: {error}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
