from setuptools import setup, find_packages

setup(
    name="syn-tool",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.1.0",
        "rich>=13.0.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
        "loguru>=0.7.0",
        "tenacity>=8.2.0",
        "requests>=2.31.0",
        "ShopifyAPI>=12.1.0",
    ],
    entry_points={
        "console_scripts": [
            "syn=syn_tool.cli:cli",
        ],
    },
)
