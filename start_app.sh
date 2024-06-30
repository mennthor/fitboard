set -e

# Note: As stated at https://flask.palletsprojects.com/en/1.1.x/api/?highlight=run#flask.Flask.run
# do not use the `app.run()` method directly from Python. Also this here is
# closer to an actual `gunicorn` invocation for example.

export FLASK_APP=fitboard:init_app
export FLASK_ENV=development
export FLASK_DEBUG=1
export DASH_DEBUG=1
poetry run flask run --port 8888
