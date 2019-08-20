from .logger import log, debug

from .models import Addresses, Rule, Host, Route, Interface


def add_rule(table_id, priority, iproute):
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


def remove_outdated(addresses: set, table: int, interface, ipr):
    """
    Applies all addresses to the specified routing table:
    removes outdated, creates all new.
    Note: This function changes addresses list.
    """
    current = ipr.get_routes(table=table)
    current = {x.dst: x for x in map(Route.fromdict, current)}
    # remove all that's not in the db
    outdated, skipped = 0, 0
    for outdated, route in enumerate(current):
        import pdb

        pdb.set_trace()
        if route not in addresses:
            route.remove()
        else:
            # route already exist, skip it in the future
            addresses.remove(route.dst)
            skipped += 1
    log("Removed <info>%s</> outdated routes, <info>%s</> skipped.", outdated, skipped)


def find_interface(ipr, name):
    interfaces = [x for x in map(Interface, ipr.get_links()) if x.name == name]
    if not interfaces:
        raise ValueError(f"Failed to find interface with name {name!r}.")
    # elif len(interfaces) > 1:
    #     raise ValueError("It can't be!")
    return interfaces[0]


# def add_routes(addresses, table, interface, ipr)

# # # # # # # # # #
# Rule exceptions #
# # # # # # # # # #


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
