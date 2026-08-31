"""Structured notification severity contract."""
from enum import Enum
class Severity(str,Enum): INFO='INFO'; WARNING='WARNING'; CRITICAL='CRITICAL'
