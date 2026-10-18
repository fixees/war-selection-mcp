"""Lua 5.4 syntax checker (pure Python, no dependencies).

Parses a chunk the way the reference compiler does and reports the first syntax
error in luac style ("'end' expected (to close 'function' at line 3) near <eof>").
While parsing it records lightweight facts used by the linter: dotted references
(calls, reads, assignments), defined names, addMod handler tables and local aliases.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

KEYWORDS = {
    "and", "break", "do", "else", "elseif", "end", "false", "for", "function", "goto", "if", "in",
    "local", "nil", "not", "or", "repeat", "return", "then", "true", "until", "while",
}
OPS3 = ("...",)
OPS2 = ("..", "==", "~=", "<=", ">=", "<<", ">>", "//", "::")
OPS1 = set("+-*/%^#&~|<>=(){}[];:,.")

BINARY_PRIORITY = {
    "or": (1, 1), "and": (2, 2),
    "<": (3, 3), ">": (3, 3), "<=": (3, 3), ">=": (3, 3), "~=": (3, 3), "==": (3, 3),
    "|": (4, 4), "~": (5, 5), "&": (6, 6), "<<": (7, 7), ">>": (7, 7),
    "..": (9, 8), "+": (10, 10), "-": (10, 10),
    "*": (11, 11), "/": (11, 11), "//": (11, 11), "%": (11, 11),
    "^": (14, 13),
}
UNARY_PRIORITY = 12
BLOCK_END = {"end", "else", "elseif", "until", "<eof>"}

_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_HEX_RE = re.compile(r"0[xX](?:[0-9a-fA-F]*\.?[0-9a-fA-F]*)(?:[pP][+-]?[0-9]+)?")
_DEC_RE = re.compile(r"(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


class LuaSyntaxError(Exception):
    def __init__(self, message: str, line: int):
        super().__init__(f"line {line}: {message}")
        self.message = message
        self.line = line


@dataclass
class Token:
    type: str  # name, keyword, number, string, op, eof
    value: str
    line: int

    def show(self) -> str:
        if self.type == "eof":
            return "<eof>"
        if self.type == "string":
            v = self.value if len(self.value) <= 30 else self.value[:30] + "..."
            return f"'{v}'"
        return f"'{self.value}'"


def _long_bracket_level(src: str, i: int) -> int:
    """At src[i] == '[': return level of '[==[' opener, or -1."""
    j = i + 1
    while j < len(src) and src[j] == "=":
        j += 1
    if j < len(src) and src[j] == "[":
        return j - i - 1
    return -1


def tokenize(src: str) -> list[Token]:
    toks: list[Token] = []
    i, n, line = 0, len(src), 1
    if src.startswith("#"):
        while i < n and src[i] != "\n":
            i += 1
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c in " \t\r\f\v":
            i += 1
            continue
        if src.startswith("--", i):
            i += 2
            if i < n and src[i] == "[":
                lvl = _long_bracket_level(src, i)
                if lvl >= 0:
                    close = "]" + "=" * lvl + "]"
                    end = src.find(close, i)
                    if end < 0:
                        raise LuaSyntaxError("unfinished long comment near <eof>", line)
                    line += src.count("\n", i, end)
                    i = end + len(close)
                    continue
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c == "[":
            lvl = _long_bracket_level(src, i)
            if lvl >= 0:
                start_line = line
                close = "]" + "=" * lvl + "]"
                end = src.find(close, i)
                if end < 0:
                    raise LuaSyntaxError("unfinished long string near <eof>", start_line)
                body = src[i + lvl + 2:end]
                line += src.count("\n", i, end)
                toks.append(Token("string", body, start_line))
                i = end + len(close)
                continue
        if c in "\"'":
            start_line = line
            j = i + 1
            buf = []
            while True:
                if j >= n or src[j] == "\n":
                    raise LuaSyntaxError("unfinished string near '" + src[i:j][:30] + "'", start_line)
                ch = src[j]
                if ch == c:
                    break
                if ch == "\\":
                    j += 1
                    if j >= n:
                        raise LuaSyntaxError("unfinished string", start_line)
                    e = src[j]
                    if e == "\n":
                        line += 1
                    elif e == "z":
                        j += 1
                        while j < n and src[j] in " \t\r\n\f\v":
                            if src[j] == "\n":
                                line += 1
                            j += 1
                        continue
                    elif e == "x":
                        if not re.match(r"[0-9a-fA-F]{2}", src[j + 1:j + 3]):
                            raise LuaSyntaxError("hexadecimal digit expected", line)
                        j += 2
                    elif e == "u":
                        m = re.match(r"\{[0-9a-fA-F]+\}", src[j + 1:])
                        if not m:
                            raise LuaSyntaxError("invalid unicode escape", line)
                        j += len(m.group(0))
                    elif e.isdigit():
                        m = re.match(r"[0-9]{1,3}", src[j:])
                        if int(m.group(0)) > 255:
                            raise LuaSyntaxError("decimal escape too large", line)
                        j += len(m.group(0)) - 1
                    elif e not in "abfnrtv\\\"'\r":
                        raise LuaSyntaxError(f"invalid escape sequence '\\{e}'", line)
                    buf.append("?")
                    j += 1
                    continue
                buf.append(ch)
                j += 1
            toks.append(Token("string", "".join(buf), start_line))
            i = j + 1
            continue
        if c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            m = _HEX_RE.match(src, i) if src.startswith(("0x", "0X"), i) else _DEC_RE.match(src, i)
            j = m.end()
            if j < n and (src[j].isalnum() or src[j] == "_" or src[j] == "."):
                k = j
                while k < n and (src[k].isalnum() or src[k] in "_."):
                    k += 1
                raise LuaSyntaxError(f"malformed number near '{src[i:k]}'", line)
            toks.append(Token("number", src[i:j], line))
            i = j
            continue
        m = _NAME_RE.match(src, i)
        if m:
            w = m.group(0)
            toks.append(Token("keyword" if w in KEYWORDS else "name", w, line))
            i = m.end()
            continue
        if src.startswith("...", i):
            toks.append(Token("op", "...", line))
            i += 3
            continue
        two = src[i:i + 2]
        if two in OPS2:
            toks.append(Token("op", two, line))
            i += 2
            continue
        if c in OPS1:
            toks.append(Token("op", c, line))
            i += 1
            continue
        raise LuaSyntaxError(f"unexpected symbol near '{c}'", line)
    toks.append(Token("eof", "<eof>", line))
    return toks


@dataclass
class Ref:
    chain: list[str]          # e.g. ["root", "unitType", "[]", "deathability", "health"]
    line: int
    kind: str                 # call | read | assign
    depth: int                # function nesting depth (0 = top level)
    method: bool = False      # last segment called with ':'


@dataclass
class ParseResult:
    refs: list[Ref] = field(default_factory=list)
    defined: set[str] = field(default_factory=set)          # global/local function and variable names
    defined_fields: set[str] = field(default_factory=set)   # last segment of `function a.b.c()` / `a.b = function`
    aliases: dict[str, list[str]] = field(default_factory=dict)
    addmod_handlers: list[tuple[str, str | None, int]] = field(default_factory=list)  # (key, handler name, line)
    addmod_calls: int = 0


class _Parser:
    def __init__(self, toks: list[Token]):
        self.t = toks
        self.p = 0
        self.res = ParseResult()
        self.depth = 0
        self.vararg = [True]  # main chunk is vararg
        self.loops = [0]

    # ---- helpers
    @property
    def cur(self) -> Token:
        return self.t[self.p]

    def peek(self, k: int = 1) -> Token:
        return self.t[min(self.p + k, len(self.t) - 1)]

    def check(self, value: str) -> bool:
        tk = self.cur
        return tk.type in ("op", "keyword") and tk.value == value

    def accept(self, value: str) -> bool:
        if self.check(value):
            self.p += 1
            return True
        return False

    def error(self, msg: str, tk: Token | None = None) -> LuaSyntaxError:
        tk = tk or self.cur
        return LuaSyntaxError(f"{msg} near {tk.show()}", tk.line)

    def expect(self, value: str, what: str | None = None, opener: str | None = None, line: int | None = None) -> None:
        if self.accept(value):
            return
        if opener and line is not None and line != self.cur.line:
            raise self.error(f"'{value}' expected (to close '{opener}' at line {line})")
        raise self.error(f"'{what or value}' expected")

    def name(self) -> str:
        tk = self.cur
        if tk.type != "name":
            raise self.error("<name> expected")
        self.p += 1
        return tk.value

    # ---- blocks
    def chunk(self) -> ParseResult:
        self.block()
        if self.cur.type != "eof":
            raise self.error("'<eof>' expected")
        return self.res

    def block_follow(self, with_until: bool = True) -> bool:
        tk = self.cur
        if tk.type == "eof":
            return True
        if tk.type == "keyword" and tk.value in ("end", "else", "elseif"):
            return True
        return with_until and tk.type == "keyword" and tk.value == "until"

    def block(self) -> None:
        while not self.block_follow():
            if self.check("return"):
                self.retstat()
                return
            self.statement()

    def retstat(self) -> None:
        self.p += 1
        if not self.block_follow() and not self.check(";"):
            self.explist()
        self.accept(";")
        if not self.block_follow():
            raise self.error("'<eof>' expected" if self.depth == 0 else "'end' expected")

    def statement(self) -> None:
        tk = self.cur
        line = tk.line
        if tk.type == "op" and tk.value == ";":
            self.p += 1
        elif tk.type == "op" and tk.value == "::":
            self.p += 1
            self.name()
            self.expect("::")
        elif tk.type == "keyword":
            v = tk.value
            if v == "if":
                self.p += 1
                self.expr()
                self.expect("then")
                self.block()
                while self.check("elseif"):
                    self.p += 1
                    self.expr()
                    self.expect("then")
                    self.block()
                if self.accept("else"):
                    self.block()
                self.expect("end", opener="if", line=line)
            elif v == "while":
                self.p += 1
                self.expr()
                self.expect("do")
                self.loop_block()
                self.expect("end", opener="while", line=line)
            elif v == "do":
                self.p += 1
                self.block()
                self.expect("end", opener="do", line=line)
            elif v == "for":
                self.p += 1
                n1 = self.name()
                if self.accept("="):
                    self.expr()
                    self.expect(",")
                    self.expr()
                    if self.accept(","):
                        self.expr()
                elif self.check(",") or self.check("in"):
                    while self.accept(","):
                        self.name()
                    self.expect("in")
                    self.explist()
                else:
                    raise self.error("'=' or 'in' expected")
                del n1
                self.expect("do")
                self.loop_block()
                self.expect("end", opener="for", line=line)
            elif v == "repeat":
                self.p += 1
                self.loops[-1] += 1
                self.block()
                self.loops[-1] -= 1
                self.expect("until", opener="repeat", line=line)
                self.expr()
            elif v == "function":
                self.p += 1
                parts = [self.name()]
                while self.accept("."):
                    parts.append(self.name())
                is_method = False
                if self.accept(":"):
                    parts.append(self.name())
                    is_method = True
                if len(parts) == 1:
                    self.res.defined.add(parts[0])
                else:
                    self.res.defined_fields.add(parts[-1])
                self.funcbody(line, is_method)
            elif v == "local":
                self.p += 1
                if self.accept("function"):
                    self.res.defined.add(self.name())
                    self.funcbody(line, False)
                else:
                    names = [self.name()]
                    self.attrib()
                    while self.accept(","):
                        names.append(self.name())
                        self.attrib()
                    self.res.defined.update(names)
                    if self.accept("="):
                        exps = self.explist()
                        if len(names) == 1 and len(exps) == 1 and exps[0] is not None:
                            self.res.aliases[names[0]] = exps[0]
            elif v == "return":
                raise self.error("'<eof>' expected")
            elif v == "break":
                self.p += 1
                if self.loops[-1] <= 0:
                    raise LuaSyntaxError(f"break outside a loop at line {line} near {self.cur.show()}", line)
            elif v == "goto":
                self.p += 1
                self.name()
            else:
                raise self.error("unexpected symbol")
        else:
            self.exprstat()

    def loop_block(self) -> None:
        self.loops[-1] += 1
        self.block()
        self.loops[-1] -= 1

    def attrib(self) -> None:
        if self.accept("<"):
            a = self.name()
            if a not in ("const", "close"):
                raise LuaSyntaxError(f"unknown attribute '{a}'", self.cur.line)
            self.expect(">")

    def funcbody(self, line: int, is_method: bool) -> None:
        self.expect("(")
        vararg = False
        if not self.check(")"):
            while True:
                if self.accept("..."):
                    vararg = True
                    break
                self.name()
                if not self.accept(","):
                    break
        self.expect(")")
        self.depth += 1
        self.vararg.append(vararg)
        self.loops.append(0)
        self.block()
        self.loops.pop()
        self.vararg.pop()
        self.depth -= 1
        self.expect("end", opener="function", line=line)

    def exprstat(self) -> None:
        start = self.cur
        chain, last, is_call = self.suffixedexp()
        if self.check("=") or self.check(","):
            targets = [(chain, last, is_call, start)]
            while self.accept(","):
                st = self.cur
                c2, l2, call2 = self.suffixedexp()
                targets.append((c2, l2, call2, st))
            self.expect("=")
            exps = self.explist()
            for idx, (c, l, call, st) in enumerate(targets):
                if call or l == "paren":
                    raise LuaSyntaxError("syntax error near '='", st.line)
                if c:
                    self.res.refs.append(Ref(c, st.line, "assign", self.depth))
                    if len(c) == 1:
                        self.res.defined.add(c[0])
                    elif idx < len(exps) and exps[idx] == ["<function>"]:
                        self.res.defined_fields.add(c[-1])
        elif not is_call:
            raise self.error("syntax error")

    # ---- expressions
    def explist(self) -> list[list[str] | None]:
        out = [self.expr()]
        while self.accept(","):
            out.append(self.expr())
        return out

    def expr(self, limit: int = 0) -> list[str] | None:
        """Returns the dotted chain if the expression is a bare reference (for aliases)."""
        tk = self.cur
        if (tk.type == "keyword" and tk.value == "not") or (tk.type == "op" and tk.value in ("-", "#", "~")):
            self.p += 1
            self.expr(UNARY_PRIORITY)
            chain = None
        else:
            chain = self.simpleexp()
        while True:
            tk = self.cur
            op = tk.value if tk.type in ("op", "keyword") else None
            prio = BINARY_PRIORITY.get(op) if op else None
            if not prio or prio[0] <= limit:
                break
            self.p += 1
            self.expr(prio[1])
            chain = None
        return chain

    def simpleexp(self) -> list[str] | None:
        tk = self.cur
        if tk.type in ("number", "string"):
            self.p += 1
            return None
        if tk.type == "keyword" and tk.value in ("nil", "true", "false"):
            self.p += 1
            return None
        if tk.type == "op" and tk.value == "...":
            if not self.vararg[-1]:
                raise self.error("cannot use '...' outside a vararg function")
            self.p += 1
            return None
        if tk.type == "op" and tk.value == "{":
            self.table()
            return None
        if tk.type == "keyword" and tk.value == "function":
            self.p += 1
            self.funcbody(tk.line, False)
            return ["<function>"]
        chain, last, is_call = self.suffixedexp()
        if chain and not is_call:
            self.res.refs.append(Ref(chain, tk.line, "read", self.depth))
            return chain
        return None

    def primaryexp(self) -> tuple[list[str] | None, str]:
        tk = self.cur
        if tk.type == "name":
            self.p += 1
            return [tk.value], "name"
        if tk.type == "op" and tk.value == "(":
            line = tk.line
            self.p += 1
            self.expr()
            self.expect(")", opener="(", line=line)
            return None, "paren"
        raise self.error("unexpected symbol")

    def suffixedexp(self) -> tuple[list[str] | None, str, bool]:
        start_line = self.cur.line
        chain, last = self.primaryexp()
        is_call = False
        while True:
            tk = self.cur
            if tk.type == "op" and tk.value == ".":
                self.p += 1
                nm = self.name()
                if chain is not None:
                    chain = chain + [nm]
                last, is_call = "field", False
            elif tk.type == "op" and tk.value == "[":
                self.p += 1
                self.expr()
                self.expect("]")
                if chain is not None:
                    chain = chain + ["[]"]
                last, is_call = "index", False
            elif tk.type == "op" and tk.value == ":":
                self.p += 1
                nm = self.name()
                full = (chain + [nm]) if chain is not None else None
                self.call_args(full, tk.line, method=True)
                chain, last, is_call = None, "call", True
            elif (tk.type == "op" and tk.value in ("(", "{")) or tk.type == "string":
                self.call_args(chain, start_line)
                chain, last, is_call = None, "call", True
            else:
                return chain, last, is_call

    def call_args(self, chain: list[str] | None, line: int, method: bool = False) -> None:
        tk = self.cur
        if chain:
            self.res.refs.append(Ref(chain, tk.line, "call", self.depth, method))
        is_addmod = chain == ["addMod"]
        if is_addmod:
            self.res.addmod_calls += 1
        if tk.type == "string":
            self.p += 1
        elif tk.type == "op" and tk.value == "{":
            self.table(collect=is_addmod)
        elif tk.type == "op" and tk.value == "(":
            if tk.line != self.t[self.p - 1].line and self.t[self.p - 1].type != "eof":
                pass  # Lua 5.2+ accepts this; ambiguity warning dropped in 5.2
            self.p += 1
            if not self.check(")"):
                first = True
                while True:
                    if first and is_addmod and self.check("{"):
                        self.table(collect=True)
                        # the table may be part of a larger expression
                        while True:
                            op = self.cur.value if self.cur.type in ("op", "keyword") else None
                            prio = BINARY_PRIORITY.get(op) if op else None
                            if not prio:
                                break
                            self.p += 1
                            self.expr(prio[1])
                    else:
                        self.expr()
                    first = False
                    if not self.accept(","):
                        break
            self.expect(")", opener="(", line=tk.line)
        else:
            raise self.error("function arguments expected")

    def table(self, collect: bool = False) -> None:
        line = self.cur.line
        self.expect("{")
        while not self.check("}"):
            tk = self.cur
            if tk.type == "op" and tk.value == "[":
                self.p += 1
                self.expr()
                self.expect("]")
                self.expect("=")
                self.expr()
            elif tk.type == "name" and self.peek().type == "op" and self.peek().value == "=":
                key = tk.value
                self.p += 2
                vt = self.cur
                val = self.expr()
                if collect:
                    handler = val[0] if val and len(val) == 1 and val[0] != "<function>" else None
                    if val == ["<function>"]:
                        handler = "<function>"
                    self.res.addmod_handlers.append((key, handler, vt.line))
            else:
                self.expr()
            if not (self.accept(",") or self.accept(";")):
                break
        self.expect("}", opener="{", line=line)


def parse(src: str) -> ParseResult:
    """Parse Lua source; raises LuaSyntaxError on the first syntax error."""
    if src.startswith("\ufeff"):
        src = src[1:]
    return _Parser(tokenize(src)).chunk()


def check(src: str) -> dict:
    try:
        parse(src)
    except LuaSyntaxError as e:
        return {"ok": False, "line": e.line, "error": e.message}
    return {"ok": True}
