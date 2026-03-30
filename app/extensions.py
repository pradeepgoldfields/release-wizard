"""Shared Flask extension instances.

Initialised without an app; bound to the app inside create_app() via the
application-factory pattern so they can be imported anywhere without a
circular-import issue.
"""

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
