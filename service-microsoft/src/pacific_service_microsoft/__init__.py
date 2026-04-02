"""service-microsoft — manages requests to and from Microsoft's ecosystem.

Handles Outlook Calendar, Outlook Mail, OneDrive, and Teams
integration for Pacific modules. Credentials are read from the
module's Solid vault via the driver.
"""

from pacific_service_microsoft.adapter import MicrosoftAdapter
from pacific_service_microsoft.calendar import MicrosoftCalendar

__all__ = ["MicrosoftAdapter", "MicrosoftCalendar"]
