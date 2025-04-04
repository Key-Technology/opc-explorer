import pytest
import asyncio
import contextlib

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


@pytest.fixture(scope="session")
def application():
    from qasync import QApplication

    app = QApplication([])
    yield app
    app.quit()
    app.deleteLater()


@pytest.fixture
async def mainwindow(application, url, async_server):
    window = Window(use_settings=False)
    window._ui.addrComboBox.setCurrentText(url)
    await window._connect()
    yield window
    await window._disconnect()
    window.deleteLater()


@pytest.fixture
def wait_for_signal():
    @contextlib.asynccontextmanager
    async def _signal_waiter(signal, *, timeout=1, check_params_callback=None):
        signal_received = asyncio.Event()
        calls = []

        def _quit_loop(*args):
            if check_params_callback is None or check_params_callback(*args):
                calls.append(args)
                signal_received.set()

        signal.connect(_quit_loop)

        yield

        try:
            await asyncio.wait_for(signal_received.wait(), timeout)
        except (TimeoutError, asyncio.TimeoutError):
            pytest.fail(
                f"Timed out waiting to receive {signal.signal.lstrip('2')} signal"
            )

    return _signal_waiter
