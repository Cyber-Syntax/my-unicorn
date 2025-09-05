"""Install template package.

This package provides Template Method pattern implementation for install operations,
reducing code duplication between different install strategies.
"""

from .factory import InstallTemplateFactory
from .install_template import InstallTemplate

__all__ = ["InstallTemplate", "InstallTemplateFactory"]
