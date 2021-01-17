"""
This is our dashboard app, now being created into the Flask server instead of
being a standalone app.
For this reason we need to put it all into an init function which is imported
into the main Flask `init_app` method.
"""

import os
from glob import glob
import base64
from io import BytesIO

import numpy as np
import matplotlib
matplotlib.use("agg")  # Non-interactive
import matplotlib.pyplot as plt
from mpl_toolkits.axisartist.parasite_axes import HostAxes, ParasiteAxes

import dash
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html

from flask_caching import Cache

import fitdecode


# Is it OK to have this globally available? Otherwise I can't use it in
# callbacks... Use a simple cache for testing, can be excahnged for something
# threadsave and more fancy I guess (see `flask_caching` package)
# Do not expire this cache, because it's used as a global data storage
_CACHE_CONFIG = {"CACHE_TYPE": "simple", "CACHE_DEFAULT_TIMEOUT": 0}
_CACHE = Cache()

# Read-only globals (is this OK to do?)
_FIT_FILE_PATHS = {
    "Auto": os.path.expanduser(
        os.path.join("~", "Documents", "Zwift", "Activities")),
}


def init_dashboard(server):
    """
    Create a Plotly Dash dashboard and register it to the Flask server.
    """
    dash_app = dash.Dash(
        server=server,
        routes_pathname_prefix="/",  # Route where our board lives
        # For themes, see https://www.bootstrapcdn.com/bootswatch/
        external_stylesheets=[dbc.themes.MINTY],
    )

    # Init a global cache to avoid loading all datasets into a global variable
    # at once
    _CACHE.init_app(server, config=_CACHE_CONFIG)

    # Init default data
    # Default Ziwft dir, dependent on Win, Linux, OSX
    data = {}
    data["FIT_FILE_LOC"] = ["Auto", _FIT_FILE_PATHS["Auto"]]
    data["FIT_FILES"] = _init_fit_file_db(_FIT_FILE_PATHS["Auto"])

    # Store defaults, the cache stores a single dict with all data
    _CACHE.set("data", data)

    # Build the dashboard layout
    _init_layout(dash_app)

    # Init callbacks on Flask app load, not globally before it is running
    _init_callbacks(dash_app)

    return dash_app.server


def _init_layout(dash_app):
    """
    Build our HTML layout on the fly using `dash_html_components`.
    """
    # Dataset selector: This row of cards floats atop the graph
    control_cards = [
        dbc.Card(
            [
                dbc.FormGroup(
                    [
                        dbc.Label("Specify Zwift Activity Folder"),
                        dbc.RadioItems(
                            options=[
                                {"label": "Auto-select", "value": "Auto"},
                                {"label": "Custom", "value": "Other"},
                            ],
                            value="Auto",
                            id="radio_fit_loc",
                        ),
                        dbc.Input(
                            id="radio_fit_loc_custom_text",
                            placeholder="Enter custom path",
                            type="text"
                        ),
                    ]
                ),
                # Used to indicate no files found at selected location
                html.Div(id="radio_fit_loc_feedback"),
            ],
            body=True,
            color="light",
        ),
        dbc.Card(
            [
                dbc.FormGroup(
                    [
                        dbc.Label("Select Dataset"),
                        dcc.Dropdown(
                            id="dropdown_dataset",
                            options=[{"label": os.path.basename(fname), "value": fname}
                                     for fname in _CACHE.get("data")["FIT_FILES"]],
                            placeholder=os.path.basename(_CACHE.get("data")["FIT_FILES"][-1]) if _CACHE.get("data")["FIT_FILES"] else "",
                            value=_CACHE.get("data")["FIT_FILES"][-1] if _CACHE.get("data")["FIT_FILES"] else None,
                        ),
                    ]
                ),
                html.Div(id="dropdown_dataset_feedback"),
            ],
            body=True,
            color="light",
        ),
    ]

    # Main graph showing the loaded FIT file, centered below card row.
    # The divs are switched on/off via the style element. Instead of the graph,
    # an alert box is displayed when the fit file is faulty and vice-versa
    graph = html.Div(
        [
            html.Div(
                [
                    html.Img(id="graph", src=""),
                ],
                id="div_graph_graph",
                style={"display": "block"}
            ),
            html.Div(
                [
                    dbc.Alert("", id="graph_alert", color="danger"),
                ],
                id="div_graph_alert",
                style={"display": "none"}
            ),
        ],
        id="div_graph"
    )

    dash_app.layout = dbc.Container(
        [
            html.H2("Viewer Board for FIT Data", style={"margin-top": 5}),
            html.Hr(),
            # dbc.Row([dbc.Col(card) for card in cards]),
            dbc.Row([dbc.Col(cntrl_card) for cntrl_card in control_cards]),
            html.Br(),
            dbc.Row([graph]),
        ],
        fluid=False,
    )


def _init_callbacks(dash_app):
    """
    Init our dashboard callbacks, this defines the board's functionality.
    """
    # Fit file dropdown callback:
    # Print selected set in `dropdown_dataset_feedback` and update plot
    @dash_app.callback(
        [dash.dependencies.Output("dropdown_dataset_feedback", "children"),
         dash.dependencies.Output("graph", "src"),
         dash.dependencies.Output("graph_alert", "children"),
         dash.dependencies.Output("div_graph_graph", "style"),
         dash.dependencies.Output("div_graph_alert", "style")],
        [dash.dependencies.Input("dropdown_dataset", "value")])
    def cb_dropdown_dataset_feedback(dropdown_val):
        # Read the date from selected file, make figure, convert to base64 and
        # feed into html.img tag. If err, display the error instead
        g_src = ""
        ga_text = ""
        dg_style = {"display": "block"}
        dga_style = {"display": "none"}
        try:
            values, units = _load_fit_file(dropdown_val)
            g_src = _make_figure(values, units)
        except IOError as err:
            ga_text = str(err)
            # Switch visibility
            dg_style, dga_style = dga_style, dg_style
            dga_style["margin"] = "auto"

        # The feedback message under the dropdown
        msg = ("Selected '{}'".format(dropdown_val)
               if dropdown_val is not None else "No dataset selected",)
        return msg, g_src, ga_text, dg_style, dga_style

    # Zwift activity folder radio select callback:
    # Search for new files if new selection is done
    @dash_app.callback(
        [dash.dependencies.Output("radio_fit_loc_feedback", "children"),
         dash.dependencies.Output("dropdown_dataset", "options"),
         dash.dependencies.Output("dropdown_dataset", "placeholder"),
         dash.dependencies.Output("dropdown_dataset", "value")],
        [dash.dependencies.Input("radio_fit_loc", "value"),
         dash.dependencies.Input("radio_fit_loc_custom_text", "value")])
    def cb_radio_fit_loc_feedback(radio_val, text_val):
        data = _CACHE.get("data")

        # Search for files at selected location
        text_val = "" if text_val is None else text_val
        if radio_val in _FIT_FILE_PATHS:
            text_val = _FIT_FILE_PATHS[radio_val]
        files = _init_fit_file_db(text_val)
        # Store new selection in cache
        data["FIT_FILE_LOC"] = [radio_val, text_val]
        data["FIT_FILES"] = files
        _CACHE.set("data", data)

        # Update fit file selector dropwdown
        opts = [{"label": os.path.basename(fname), "value": fname}
                for fname in data["FIT_FILES"]]
        placeholder = os.path.basename(
            data["FIT_FILES"][-1]) if data["FIT_FILES"] else ""
        dropwdown_val = data["FIT_FILES"][-1] if data["FIT_FILES"] else None

        if not os.path.isdir(data["FIT_FILE_LOC"][1]):
            msg = "Path '{}' not valid".format(data["FIT_FILE_LOC"][1])
        else:
            msg = "{} FIT files found at '{}'".format(
                len(data["FIT_FILES"]), data["FIT_FILE_LOC"][1])
        return msg, opts, placeholder, dropwdown_val


def _init_fit_file_db(fit_db_path):
    """
    Search the given Zwift activity path for `*.fit` activity files.

    Parameters
    ----------
    fit_db_path : str
        Fully resolved name where the `*.fit` files can be found.

    Returns
    -------
    fit_files : list
        Sorted list of all found `*.fit` files in the given folder.
    """
    fit_files = sorted(glob(os.path.join(fit_db_path, "*.fit")))
    fit_files = [f for f in fit_files
                 if not os.path.basename(f).startswith("inProgress")]
    return fit_files


def _load_fit_file(fname):
    """
    Returns values as `name: list of values` pairs and dict of `name: unit name`
    for the FIT file with the given filename.

    Parameters
    ----------
    fname : str
        Fully resolved filename of the FIT file to load.

    Returns
    -------
    values : dict
        Dictionary with parameter names as keys and a list of all values stored
        in the fit file.
    units : dict
        Dictionary with parameter names as keys and unit names as values. Has
        same keys as `values`.
    """
    values, units = {}, {}
    try:
        with fitdecode.FitReader(fname) as fit:
            # The yielded frame object is of one of the following types:
            # * fitdecode.FitHeader
            # * fitdecode.FitDefinitionMessage
            # * fitdecode.FitDataMessage
            # * fitdecode.FitCRC
            # We want the data frames
            for frame in fit:
                if not isinstance(frame, fitdecode.FitDataMessage):
                    continue

                # The record frames contain the wanted data columns
                if frame.name == "record":
                    # Append data to collection.
                    # Note: Some seem to be doubled but None? Ignore them
                    _values = [f.value for f in frame.fields]
                    _names = [f.name for i, f in enumerate(frame.fields)
                              if _values[i] is not None]
                    _units = [f.units for i, f in enumerate(frame.fields)
                              if _values[i] is not None]
                    _values = [
                        f.value for f in frame.fields if f.value is not None]
                    # Init
                    if not values:
                        values = {name: [] for name in _names}
                        units = {
                            name: unit for name, unit in zip(_names, _units)}
                    # Check consistency
                    if (len(_names) != len(values)
                            or not all([n in values for n in _names])):
                        print(_names)
                        print(_values)
                        print(_units)
                        raise ValueError("Inconsistent columns in FIT records.")
                    # Store
                    [values[n].append(v) for n, v in zip(_names, _values)]
                elif frame.name == "session":
                    # This contains ride summaries and potentially integer
                    # encoded course and world name. Currently not used
                    continue

    except Exception as err:
        raise IOError("Invalid FIT file entries: {}".format(err))

    # Enhance with a normalized distance and time fields
    if "altitude" in values:
        values["altitude_norm"] = [
            d - values["altitude"][0] for d in values["altitude"]]
        units["altitude_norm"] = units["altitude"]
    if "timestamp" in values:
        values["time_norm"] = [
            (d - values["timestamp"][0]).seconds for d in values["timestamp"]]
        units["time_norm"] = "s"
    if "speed" in values:
        values["speed_kmh"] = [d * 3.6 for d in values["speed"]]
        units["speed_kmh"] = "km/h"

    return values, units


def _make_figure(values, units):
    """
    Creates the main graph plot in matplotlib.
    """
    fig = plt.figure(figsize=(12, 5))
    if values:
        times = np.array(values["time_norm"]) / 60.
        host = HostAxes(fig, [0.15, 0.1, 0.65, 0.8])
        plot_names = ["power", "altitude_norm", "cadence", "speed_kmh"]
        for i, name in enumerate(plot_names):
            if i == 0:
                ax = host
                ax.axis["right"].set_visible(False)
            else:
                ax = ParasiteAxes(host, sharex=host)
                host.parasites.append(ax)
                ax.axis["right"].set_visible(True)
                if i == 1:
                    ax.axis["right"].major_ticklabels.set_visible(True)
                    ax.axis["right"].label.set_visible(True)
                else:
                    new_axisline = ax.get_grid_helper().new_fixed_axis
                    ax.axis["right2"] = new_axisline(
                        loc="right", axes=ax, offset=(60 * (i - 1), 0))

            p, = ax.plot(times, values[name], label=name)
            ax.set_ylabel("{} in {}".format(name, units[name]))
            if not any([v < 0 for v in values[name]]):
                ax.set_ylim(0, None)
            else:
                ax.set_ylim(np.amin(values[name]), None)
                ax.axhline(0, 0, 1, ls=":", lw=1, c=p.get_color())

        host.set_xlim(times[0], times[-1])
        # host.set_xlabel("Time in {}".format(units["time_norm"]))
        host.set_xlabel("Time in min.")
        _ncol = int(fig.get_size_inches()[0] / 3)  # A little heuristic, 3in per label
        host.legend(ncol=_ncol, bbox_to_anchor=(
            0.5, 1.025 + len(plot_names) // _ncol * 0.05), loc="center")
        fig.add_axes(host)
    else:
        # Empty figure with text that no data is there
        ax = fig.add_axes([0, 0, 1, 1])
        ax.text(0.5, 0.5, "No data to show", ha="center", va="center")
    # Convert
    out_img = BytesIO()
    fig.savefig(out_img, format="png")
    fig.clf()
    plt.close("all")
    out_img.seek(0)  # Rewind file
    encoded = base64.b64encode(out_img.read()).decode("ascii").replace("\n", "")
    return "data:image/png;base64,{}".format(encoded)
