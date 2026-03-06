from server import app, init_db

# Ensure DB and tables exist when app loads.
init_db()
application = app

