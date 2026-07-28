from __future__ import annotations

from app.services.parsers.base import EmailJobParser, EmailParseContext
from app.services.parsers.generic import GenericEmailParser
from app.services.parsers.linkedin import LinkedInEmailParser


class ParserRegistry:
    def __init__(self, parsers: list[EmailJobParser] | None = None) -> None:
        self._parsers = parsers or [
            LinkedInEmailParser(),
            GenericEmailParser(),
        ]

    def select_parser(self, context: EmailParseContext) -> EmailJobParser | None:
        for parser in self._parsers:
            if parser.can_parse(context):
                return parser
        return None

    def register(self, parser: EmailJobParser) -> None:
        self._parsers.insert(0, parser)
