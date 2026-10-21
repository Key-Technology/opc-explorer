from setuptools import find_packages, setup


setup(
    name="opc-explorer",
    version="0.9.2",
    description="OPC Explorer",
    author="Key Technology",
    python_requires=">=3.8,<3.12",  # Only expand this as we add tests for them
    url="https://github.com/Key-Technology/opc-explorer",
    packages=find_packages(include=["uaclient", "uaclient.*"]),
    license="GNU General Public License",
    install_requires=["asyncua", "opcua-widgets>=0.6.0", "PyQt5"],
    entry_points={"console_scripts": ["opc-explorer = uaclient.mainwindow:main"]},
)
