from setuptools import setup, find_packages

setup(
    name="csi_acquisition",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "colorama==0.4.6",
        "influxdb-client==1.46.0",
        "pydantic==2.9.2",
        "PyYAML==6.0.2",
        "pyserial==3.5",
        "numpy==2.0.1"
    ]
)
