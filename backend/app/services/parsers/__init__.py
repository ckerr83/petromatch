from app.services.parsers.base import EmailJobParser, EmailParseContext, ParsedOpportunity
from app.services.parsers.generic import GenericEmailParser
from app.services.parsers.linkedin import LinkedInEmailParser
from app.services.parsers.registry import ParserRegistry

__all__ = [
    "EmailJobParser",
    "EmailParseContext",
    "GenericEmailParser",
    "LinkedInEmailParser",
    "ParsedOpportunity",
    "ParserRegistry",
]
