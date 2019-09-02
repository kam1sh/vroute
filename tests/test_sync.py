from vroute.routing import RouteManager, RouterosManager


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
    RouteManager.route.assert_called_once_with("del", dst="1.2.3.4/32", oif=7, table=10)
    RouterosManager._rm_route.assert_called_once_with("*1")
