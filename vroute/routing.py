from .logger import log, debug

from .models import Rule


def add_rule(priority, table_id, iproute):
    """ Adds new rule for all addresses with lookup to a specified table. """
    rules = iproute.get_rules()
    targets = []
    for rule in map(Rule.fromdict, rules):
        if rule.table == table_id:
            targets.append(rule)
    if not targets:
        # create new rule if there is no any
        Rule(table=table_id, priority=priority).create(iproute)
    elif len(targets) == 1:
        if targets[0].priority == priority:
            raise RuleExistsError(targets[0])
        else:
            raise DifferentRuleExists(targets[0])
    else:
        raise MultipleRulesExists(targets)


def add_routes(query, session, ip, config):
    table_name = config.get("vpn.rule.name")
    for host in query(Host):
        if not host.expires or host.expires < pendulum.now():
            resolved = host.resolve()
            session.add_all(resolved)
            session.commit()
        for addr in query(Address).filter(Address.host_id == host.id):
            ip.route("add", dst=f"{addr}/32", dev="tun0", table=config)


class RuleError(ValueError):
    """ Base exception for rule errors. """

    def __init__(self, rule: Rule):
        self.rule = rule
        super().__init__(self.format())

    def format(self):
        return ""


class RuleExistsError(RuleError):
    def format(self):
        return "Rule already exists, skipping."


class DifferentRuleExists(RuleExistsError):
    def format(self):
        return f"Rule already exists with priority {self.rule.priority}."


class MultipleRulesExists(RuleExistsError):
    def format(self):
        return (
            "There's more than one rule for the target table."
            " I have a bad feeling about this."
        )
