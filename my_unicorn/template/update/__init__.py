"""Template package for update operations.

This package contains the Template Method pattern implementation for update operations,
along with Strategy and Command patterns for app selection and operations.
"""

from .update_template import UpdateTemplate
from .selectors import AppSelector, AllAppsSelector, SpecificAppsSelector
from .operations import UpdateOperation, CheckOnlyOperation, UpdateActionOperation
from .factory import UpdateTemplateFactory

__all__ = [
    "UpdateTemplate",
    "AppSelector", 
    "AllAppsSelector",
    "SpecificAppsSelector", 
    "UpdateOperation",
    "CheckOnlyOperation",
    "UpdateActionOperation",
    "UpdateTemplateFactory",
]
