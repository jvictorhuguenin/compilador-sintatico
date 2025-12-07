import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Callable, List, Optional


class LexToken(SimpleNamespace):
    pass


@dataclass
class _Rule:
    name: str
    pattern: str
    func: Optional[Callable]


class PlyLexer:
    def __init__(self, module):
        self.module = module
        self.rules: List[_Rule] = []
        self.error_func = getattr(module, "t_error", None)
        self.ignore = getattr(module, "t_ignore", "")
        self.lineno = 1
        self._build_rules()
        self._build_regex()
        self.text = ""
        self.pos = 0

    def _build_rules(self):
        for name, value in self.module.__class__.__dict__.items():
            if not name.startswith("t_"):
                continue
            if name in {"t_error", "t_ignore"}:
                continue
            if callable(value):
                pattern = value.__doc__
                func = getattr(self.module, name)
            else:
                pattern = value
                func = None
            if not pattern:
                continue
            rule_name = name[2:]
            self.rules.append(_Rule(rule_name, pattern, func))

    def _build_regex(self):
        parts = [f"(?P<{rule.name}>{rule.pattern})" for rule in self.rules]
        if self.ignore:
            ignore_pattern = f"[{re.escape(self.ignore)}]+"
            parts.append(f"(?P<IGNORE>{ignore_pattern})")
        self.regex = re.compile("|".join(parts), re.MULTILINE)
        self.rule_map = {rule.name: rule for rule in self.rules}

    def input(self, text: str):
        self.text = text
        self.pos = 0

    def token(self):
        text_len = len(self.text)
        while self.pos < text_len:
            match = self.regex.match(self.text, self.pos)
            if not match:
                if self.error_func:
                    tok = LexToken()
                    tok.value = self.text[self.pos]
                    tok.lineno = self.lineno
                    tok.lexer = self
                    self.error_func(tok)
                self.pos += 1
                continue

            self.pos = match.end()
            name = match.lastgroup
            value = match.group(name)

            if name == "IGNORE":
                self.lineno += value.count("\n")
                continue

            rule = self.rule_map[name]
            tok = LexToken()
            tok.type = name
            tok.value = value
            tok.lineno = self.lineno
            tok.lexer = self

            if rule.func:
                result = rule.func(tok)
                if result is None:
                    continue
                return result

            self.lineno += value.count("\n")
            return tok
        return None


def lex(module=None):
    if module is None:
        raise SyntaxError("lex() requires a module parameter")
    return PlyLexer(module)
