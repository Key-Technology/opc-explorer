import pytest
import asyncio

from asyncua import Server
from asyncua.sync import Server as SyncServer

from uaclient.mainwindow import Window


@pytest.fixture(scope="module")
def url():
    yield "opc.tcp://localhost:48401/freeopcua/server/"


@pytest.fixture
async def async_server(url):
    server = Server()
    await server.init()
    server.set_endpoint(url)
    await server.start()
    yield server
    await server.stop()


@pytest.fixture(scope="module")
def server(url):
    server = SyncServer()
    server.set_endpoint(url)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def client(qtbot, url):
    client = Window()
    qtbot.addWidget = client
    client.ui.addrComboBox.setCurrentText(url)
    client.connect()
    yield client
    client.disconnect()


@pytest.fixture
def wait_for_signal():
    async def _signal_waiter(signal, *, timeout=1, check_params_callback=None):
        signal_received = asyncio.Event()
        calls = []

        def _quit_loop(*args):
            if check_params_callback is None or check_params_callback(*args):
                calls.append(args)
                signal_received.set()

        signal.connect(_quit_loop)

        try:
            await asyncio.wait_for(signal_received.wait(), timeout)
        except (TimeoutError, asyncio.TimeoutError):
            pytest.fail(
                f"Timed out waiting to receive {signal.signal.lstrip('2')} signal"
            )

        return calls

    return _signal_waiter
