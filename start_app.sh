set -e

# Note: As stated at https://flask.palletsprojects.com/en/1.1.x/api/?highlight=run#flask.Flask.run
# do not use the `app.run()` method directly from Python. Also this here is
# closer to an actual `gunicorn` invocation for example.

export FLASK_APP=fitboard:init_app
export FLASK_ENV=development
poetry run flask run
