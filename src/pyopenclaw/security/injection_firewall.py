import re
import logging
from dataclasses import dataclass, field
from typing import List
from pyopenclaw.config import FirewallConfig

logger = logging.getLogger(__name__)

class InjectionDetected(Exception):
    def __init__(self, patterns: List[str]):
        self.patterns = patterns
        super().__init__(f"Prompt injection detected: {patterns}")

@dataclass
class ScanResult:
    clean: bool
    patterns: List[str] = field(default_factory=list)

class InjectionFirewall:
    def __init__(self, config: FirewallConfig):
        self.config = config
        self._patterns = {
            "ignore_instructions": re.compile(r"ignore (previous|all|above) instructions", re.IGNORECASE),
            "act_as": re.compile(r"(you are now|act as|pretend you are)", re.IGNORECASE),
            "system_tag": re.compile(r"(\[system\]|<system>|###system###)", re.IGNORECASE),
            "forget_instructions": re.compile(r"forget your instructions", re.IGNORECASE),
            "jailbreak": re.compile(r"(jailbreak|DAN mode)", re.IGNORECASE),
        }

    def scan(self, text: str) -> ScanResult:
        patterns = self._detect_prompt_override_patterns(text)
        
        if not patterns:
            return ScanResult(clean=True)
            
        if self.config.mode == "block":
            logger.warning(f"Blocking prompt injection: {patterns}")
            raise InjectionDetected(patterns)
        else: # mode == "flag"
            logger.info(f"Flagging prompt injection: {patterns}")
            return ScanResult(clean=False, patterns=patterns)

    def _detect_prompt_override_patterns(self, text: str) -> List[str]:
        matched = []
        for name, regex in self._patterns.items():
            if regex.search(text):
                matched.append(name)
        return matched
