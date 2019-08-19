from copy import deepcopy
import pytest
from vroute.logger import logger
from vroute import routing

import pyroute2

from . import CommandTester
from .test_vroute import example_data

# # # # # # # # # #
# 'sync' command  #
# # # # # # # # # #

# rule with priority 40 and table id 10
# example dictionary from the iproute.get_rules()
TARGET_RULE = {
    "action": 1,
    "attrs": [
        ("FRA_TABLE", 10),
        ("FRA_SUPPRESS_PREFIXLEN", 4294967295),
        ("FRA_PRIORITY", 40),
    ],
    "dst_len": 0,
    "event": "RTM_NEWRULE",
    "family": 2,
    "flags": 0,
    "header": {
        "error": None,
        "flags": 2,
        "length": 52,
        "pid": 9950,
        "sequence_number": 255,
        # "stats": Stats(qsize=0, delta=0, delay=0),
        "type": 32,
    },
    "res1": 0,
    "res2": 0,
    "src_len": 0,
    "table": 10,  # < table id
    "tos": 0,
}


@pytest.fixture(scope="function")
def example_rule():
    return deepcopy(TARGET_RULE)


# response from iproute.rule("add")
RULE_RESPONSE = (
    {
        "header": {
            "length": 36,
            "type": 2,
            "flags": 256,
            "sequence_number": 255,
            "pid": 12840,
            "error": None,
            # "stats": Stats(qsize=0, delta=0, delay=0),
        },
        "event": "NLMSG_ERROR",
    },
)


@pytest.yield_fixture(scope="function")
def ipr():
    with pyroute2.IPRoute() as obj:
        yield obj


def test_ruleobj():
    rule = routing.Rule.fromdict(TARGET_RULE)
    assert rule.table == 10
    assert rule.priority == 40


def mock_rules(ipr, mocker, get_rules=None, rule=None):
    mocker.patch.object(ipr, "get_rules")
    ipr.get_rules.return_value = get_rules or tuple()
    mocker.patch.object(ipr, "rule")
    ipr.rule.return_value = rule


def test_check_rule_empty(ipr, mocker):
    mock_rules(ipr, mocker)
    routing.add_rule(table_id=10, priority=40, iproute=ipr)
    ipr.get_rules.assert_called_once()
    ipr.rule.assert_called_once()


def test_check_rule_exists(ipr, mocker):
    mock_rules(ipr, mocker, get_rules=(TARGET_RULE,))
    with pytest.raises(routing.RuleExistsError):
        routing.add_rule(table_id=10, priority=40, iproute=ipr)
    ipr.get_rules.assert_called_once()
    assert not ipr.rule.called
