#!/usr/bin/env python3
#
# This is just a demo server for playing with the UI if you don't
# have a real server to play with.

import asyncio
import random
import signal

from asyncua import Server

_URL = "opc.tcp://localhost:48400/opc-explorer/server"


async def _generate_values(server: Server, shutdown_event: asyncio.Event):
    index = await server.register_namespace("demo")

    big_folder = await server.nodes.objects.add_folder(index, "Big")
    for n in range(1, 1000):
        if shutdown_event.is_set():
            return
        variable = await big_folder.add_variable(index, f"Variable {n}", n)

    dynamic_folder = await server.nodes.objects.add_folder(index, "Dynamic")
    variable = await dynamic_folder.add_variable(index, "TestVariable", 42)

    while not shutdown_event.is_set():
        await variable.write_value(random.randint(1, 100))
        await asyncio.sleep(1)


async def main():
    shutdown_event = asyncio.Event()

    def _shutdown(signal_received, frame):
        print("Shutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, _shutdown)

    server = Server()
    await server.init()
    server.set_endpoint(_URL)
    await server.start()

    await asyncio.gather(_generate_values(server, shutdown_event))
    await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
