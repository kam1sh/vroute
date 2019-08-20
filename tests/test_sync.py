from copy import deepcopy
import pytest
from vroute.logger import logger
from vroute.models import Interface
from vroute import routing

import pyroute2

from . import CommandTester
from .test_vroute import example_data
from .samples import ROUTE, RULE, RULE_RESPONSE, INTERFACE

# # # # # # # # # #
# 'sync' command  #
# # # # # # # # # #


@pytest.fixture(scope="function")
def rule():
    return deepcopy(RULE)


@pytest.fixture(scope="function")
def rule_response():
    return deepcopy(RULE_RESPONSE)


@pytest.fixture(scope="function")
def route():
    return deepcopy(ROUTE)


@pytest.fixture(scope="function")
def interface():
    return deepcopy(INTERFACE)


@pytest.yield_fixture(scope="function")
def ipr():
    with pyroute2.IPRoute() as obj:
        obj.get_routes()
        yield obj


def test_ruleobj(rule):
    rule = routing.Rule.fromdict(rule)
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


def test_check_rule_exists(ipr, mocker, rule):
    mock_rules(ipr, mocker, get_rules=(rule,))
    with pytest.raises(routing.RuleExistsError):
        routing.add_rule(table_id=10, priority=40, iproute=ipr)
    ipr.get_rules.assert_called_once()
    assert not ipr.rule.called


def test_interface(interface):
    iface = Interface(interface)
    assert iface.name == "tun0"
    assert iface.state == "up"
    assert iface.num == 7

# TODO sync 1 new route
# mock get_routes and add_route

# TODO remove 1 outdated route
