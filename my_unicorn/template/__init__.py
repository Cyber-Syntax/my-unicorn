"""Template package for update operations.

This package contains the Template Method pattern implementation for update and install operations
along with Strategy and Command patterns for app selection and operations.
"""

from .update.update_template import UpdateTemplate
from .update.selectors import AppSelector, AllAppsSelector, SpecificAppsSelector
from .update.operations import UpdateOperation, CheckOnlyOperation, UpdateActionOperation
from .update.factory import UpdateTemplateFactory
from .install.factory import InstallTemplateFactory
from .install.install_template import InstallTemplate


__all__ = [
    "InstallTemplate",
    "InstallTemplateFactory",
    "UpdateTemplate",
    "AppSelector", 
    "AllAppsSelector",
    "SpecificAppsSelector", 
    "UpdateOperation",
    "CheckOnlyOperation",
    "UpdateActionOperation",
    "UpdateTemplateFactory",
]

