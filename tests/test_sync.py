from copy import deepcopy
import pytest
from vroute.models import Interface
from vroute import routing
from vroute.routing import RouteManager, RouterosManager

import pyroute2


# # # # # # # # # #
# 'sync' command  #
# # # # # # # # # #


# @pytest.fixture(scope="function")
# def rule():
#     return deepcopy(RULE)
#
#
# @pytest.fixture(scope="function")
# def rule_response():
#     return deepcopy(RULE_RESPONSE)
#
#
# @pytest.fixture(scope="function")
# def route():
#     return deepcopy(ROUTE)
#
#
# @pytest.fixture(scope="function")
# def interface():
#     return deepcopy(INTERFACE)
#
#
# @pytest.yield_fixture(scope="function")
# def ipr():
#     with pyroute2.IPRoute() as obj:
#         obj.get_routes()
#         yield obj
#
#
# def test_ruleobj(rule):
#     rule = routing.Rule.fromdict(rule)
#     assert rule.table == 10
#     assert rule.priority == 40
#
#
# def mock_rules(ipr, mocker, get_rules=None, rule=None):
#     mocker.patch.object(ipr, "get_rules")
#     ipr.get_rules.return_value = get_rules or tuple()
#     mocker.patch.object(ipr, "rule")
#     ipr.rule.return_value = rule
#
#
# def test_check_rule_empty(ipr, mocker):
#     mock_rules(ipr, mocker)
#     routing.add_rule(table_id=10, priority=40, iproute=ipr)
#     ipr.get_rules.assert_called_once()
#     ipr.rule.assert_called_once()
#
#
# def test_check_rule_exists(ipr, mocker, rule):
#     mock_rules(ipr, mocker, get_rules=(rule,))
#     with pytest.raises(routing.RuleExistsError):
#         routing.add_rule(table_id=10, priority=40, iproute=ipr)
#     ipr.get_rules.assert_called_once()
#     assert not ipr.rule.called
#
#
# def test_interface(interface):
#     iface = Interface(interface)
#     assert iface.name == "tun0"
#     assert iface.state == "up"
#     assert iface.num == 7
#


async def test_sync_initial(helpers):
    helpers.add_host("example.com", "1.2.3.4")
    helpers.mock_rule(exists=False)
    helpers.mock_interface()
    # no routes exist
    helpers.mock_routes()
    helpers.mock_ros_routes()
    await helpers.post("/sync")
    mgr = RouteManager
    mgr.get_rules.assert_called_once_with()
    mgr.rule.assert_called_once_with(action="add", priority=40, table=10)
    mgr.get_routes.assert_called_once_with(table=10)
    mgr.route.assert_called_once_with("add", dst="1.2.3.4/32", oif=7, table=10)
    mgr = RouterosManager
    mgr.get_raw_routes.assert_called_once_with()
    mgr._add_route.assert_called_once_with(
        {"dst-address": "1.2.3.4/32", "gateway": "127.0.0.2", "routing-mark": "vpn"}
    )

async def test_sync_append(helpers):
    helpers.add_host("example.com", "1.2.3.4")
    helpers.add_host("example.org", "1.2.3.5")
    helpers.mock_rule(exists=True)
    helpers.mock_interface()
    helpers.mock_routes("1.2.3.4")
    helpers.mock_ros_routes("1.2.3.4")
    await helpers.post("/sync")
    assert not RouteManager.rule.called
    RouteManager.route.assert_called_once_with("add", dst="1.2.3.5/32", oif=7, table=10)
    RouterosManager._add_route.assert_called_once_with(
        {"dst-address": "1.2.3.5/32", "gateway": "127.0.0.2", "routing-mark": "vpn"}
    )

async def test_sync_none(helpers):
    helpers.add_host("example.com", "1.2.3.4")
    helpers.mock_rule(exists=True)
    helpers.mock_interface()
    helpers.mock_routes("1.2.3.4")
    helpers.mock_ros_routes("1.2.3.4")
    await helpers.post("/sync")
    assert not RouteManager.route.called
    assert not RouterosManager._add_route.called

async def test_purge(helpers):
    # helpers.add_host("example.com", "1.2.3.4")
    helpers.mock_rule()
    helpers.mock_interface()
    helpers.mock_routes("1.2.3.4")
    helpers.mock_ros_routes("1.2.3.4")
    await helpers.post("/purge")
    RouteManager.route.assert_called_once_with("del", dst='1.2.3.4/32', oif=7, table=10)
    RouterosManager._rm_route.assert_called_once_with("*1")
