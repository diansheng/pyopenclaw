import json
import logging
from pathlib import Path
from pyopenclaw.config import ACLConfig

logger = logging.getLogger(__name__)

class ChannelACL:
    def __init__(self, config: ACLConfig, rules_file: str = "acl.json"):
        self.config = config
        self.rules_file = Path(rules_file)
        self._rules = {}
        self._load_rules()

    def _load_rules(self):
        if self.rules_file.exists():
            try:
                with open(self.rules_file, "r") as f:
                    self._rules = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse ACL rules from {self.rules_file}")
                self._rules = {}
        else:
            self._rules = {}

    def _save_rules(self):
        try:
            with open(self.rules_file, "w") as f:
                json.dump(self._rules, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save ACL rules to {self.rules_file}: {e}")

    def is_allowed(self, channel: str, sender_id: str) -> bool:
        # Check specific rule: (channel, sender_id)
        key = f"{channel}:{sender_id}"
        if key in self._rules:
            return self._rules[key]
        
        # Check channel-wide rule: (channel, "*")
        wildcard_key = f"{channel}:*"
        if wildcard_key in self._rules:
            return self._rules[wildcard_key]
            
        # Default policy
        return self.config.default_policy == "allow"

    def add_rule(self, channel: str, sender_id: str, allow: bool) -> None:
        key = f"{channel}:{sender_id}"
        self._rules[key] = allow
        self._save_rules()
