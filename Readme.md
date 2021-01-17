# Simple dashboard for viewing Zwift activity files

This is a simple Python [Flask](https://flask.palletsprojects.com/en/1.1.x/) app with a [Plotly](https://plotly.com/dash/) Dashboard in it, that can plot the `*.fit` activity files from your OSX or Windows [Zwift](zwift.com) activity folder.
It is neither sophisticated or well tested and only meant to show a bit more detail than in the companion app.

Note: Now that I write this, I think I just misused Flask and Dash as a GUI tool, because this is meant to be used locally...
Maybe I should look into Qt or something.

## Installation

The project uses `poetry` for dependency management.
If you don't have `poetry` install it using `pip install poetry` or see the [official manual](https://python-poetry.org/docs/).

To install and run this project with basically zero interference of your Python installation (other than needing `poetry`) do
```
$ cd where/this/shall/be/stored
$ git clone https://github.com/mennthor/fitboard
$ cd fitboard
$ poetry install
$ chmod +x start_app.sh
$ start_app.sh
```
This runs the dashboard in a Flask development server.
Open the browser, go to `127.0.0.1:5000` and see if this works for you.
The gif below shows how it looks on my machine, chances are non-zero however it does not look or work for you as in the example.
