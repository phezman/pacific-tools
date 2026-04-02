"""service-google — manages requests to and from Google's ecosystem.

Handles Google Calendar, Gmail, Google Drive, and Google Meet
integration for Pacific modules. Credentials are read from the
module's Solid vault via the driver.
"""

from pacific_service_google.adapter import GoogleAdapter
from pacific_service_google.calendar import GoogleCalendar

__all__ = ["GoogleAdapter", "GoogleCalendar"]
