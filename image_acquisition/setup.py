from setuptools import setup, find_packages

setup(
    name="image_acquisition",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "colorama==0.4.6",
        "influxdb-client==1.46.0",
        "opencv-python==4.10.0.84",
        "pydantic==2.9.2",
        "PyYAML==6.0.2",
    ]
)
