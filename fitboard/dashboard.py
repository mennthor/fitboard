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
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objects as go

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
    _CACHE.set("ynames", ["power"])

    # Build the dashboard layout
    _init_layout(dash_app)

    # Init callbacks on Flask app load, not globally before it is running
    _init_callbacks(dash_app)

    print("Dash app created")

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
        html.Div(
            [
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
                html.Br(),
                dbc.Card(
                    [
                        dbc.FormGroup(
                            [
                                dbc.Label("Toggle which data to show"),
                                dbc.Checklist(
                                    options=[
                                        {"label": "Power", "value": "power"},
                                        {"label": "Speed", "value": "speed_kmh"},
                                        {"label": "Cadence", "value": "cadence"},
                                        {"label": "Altitude", "value": "altitude_norm"},
                                    ],
                                    value=_CACHE.get("ynames"),
                                    id="switches_graph",
                                    switch=True,
                                    inline=True,
                                ),
                            ]
                        ),
                        html.Div(id="switches_graph_feedback"),
                    ],
                    body=True,
                    color="light",
                ),
            ]
        )
    ]

    # Main graph showing the loaded FIT file, centered below card row.
    # The divs are switched on/off via the style element. Instead of the graph,
    # an alert box is displayed when the fit file is faulty and vice-versa
    graph = html.Div(
        [
            html.Div(
                [
                    # html.Img(id="graph", src=""),
                    dcc.Graph(figure=go.Figure(), id="graph")
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
    # Plot y value selector callback
    # Update plot based on selected y values
    # @dash_app.callback(
    #     [Output("graph", "fig")],
    #     [Input("switches_graph", "value")])
    # def cb_switch_ynames(switch_vals):
    #     print("In cb_switch_ynames")
    #     if not switch_vals:
    #         fig = go.Figure()  # Empty figure if nothing selected
    #     else:
    #         fig = _make_figure(
    #             _CACHE.get("values"), _CACHE.get("units"), switch_vals)
    #     return fig
    # WHY DOES THIS CALLBACK BLOCK EVERYTHING IF FIG OUTPUT IS ADDED???
    @dash_app.callback(
        [Output("switches_graph_feedback", "children"),
         ],
        [Input("switches_graph", "value")])
    def cb_switch_ynames(switch_vals):
        print("In cb_switch_ynames")
        fig = _make_figure(
            _CACHE.get("values"), _CACHE.get("units"), switch_vals)
        return (", ".join(switch_vals),)  # , go.Figure()

    # Fit file dropdown callback:
    # Print selected set in `dropdown_dataset_feedback` and update plot
    @dash_app.callback(
        [Output("dropdown_dataset_feedback", "children"),
         Output("graph", "figure"),
         Output("graph_alert", "children"),
         Output("div_graph_graph", "style"),
         Output("div_graph_alert", "style")],
        [Input("dropdown_dataset", "value")])
    def cb_dropdown_dataset(dropdown_val):
        # Read the date from selected file, make figure, convert to base64 and
        # feed into html.img tag. If err, display the error instead
        print("In cb_dropdown_dataset")
        ga_text = ""
        dg_style = {"display": "block"}
        dga_style = {"display": "none"}
        try:
            values, units = _load_fit_file(dropdown_val)
            fig = _make_figure(values, units, _CACHE.get("ynames"))
        except IOError as err:
            fig = go.Figure()  # Dummy, will be hidden anyway
            ga_text = str(err)
            # Switch visibility
            dg_style, dga_style = dga_style, dg_style
            dga_style["margin"] = "auto"

        # The feedback message under the dropdown
        msg = ("Selected '{}'".format(dropdown_val)
               if dropdown_val is not None else "No dataset selected",)
        return msg, fig, ga_text, dg_style, dga_style

    # Zwift activity folder radio select callback:
    # Search for new files if new selection is done
    @dash_app.callback(
        [Output("radio_fit_loc_feedback", "children"),
         Output("dropdown_dataset", "options"),
         Output("dropdown_dataset", "placeholder"),
         Output("dropdown_dataset", "value")],
        [Input("radio_fit_loc", "value"),
         Input("radio_fit_loc_custom_text", "value")])
    def cb_radio_fit_loc(radio_val, text_val):
        print("In cb_radio_fit_loc")
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
    print("In _init_file_db")
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
    print("In _load_fit_file")
    print(fname)
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
    # This breaks if days are involved...
    if "timestamp" in values:
        values["time_norm"] = [
            (d - values["timestamp"][0]).seconds for d in values["timestamp"]]
        units["time_norm"] = "s"
    if "speed" in values:
        values["speed_kmh"] = [d * 3.6 for d in values["speed"]]
        units["speed_kmh"] = "km/h"
    # Convert from semicircles to degrees
    if "position_long" in values:
        values["pos_lon_deg"] = [
            d * (180. / 2**31) for d in values["position_long"]]
        units["pos_lon_deg"] = "degree"
    if "position_lat" in values:
        values["pos_lat_deg"] = [
            d * (180. / 2**31) for d in values["position_lat"]]
        units["pos_lat_deg"] = "degree"

    _CACHE.set("values", values)
    _CACHE.set("units", units)

    return values, units


def _make_figure(values, units, ynames=["power"]):
    fig = go.Figure()

    print("In _make_figure")

    if values:
        print(len(values))
        print(ynames)
        ax_colors = ["#1f77b4", "#ff7f0e", "#d62728", "#9467bd"]
        # Time in minutes
        times = np.array(values["time_norm"]) / 60.
        # We need to make room for all the potential extra axes
        _offset = 0.1
        domain_cuts = max(0, (len(ynames) - 1) * _offset)

        # Plot each name's data set
        yaxes_props = {}
        for i, name in enumerate(ynames):
            # First value is drawn to the left main axis, all others are getting
            # a new axis on the right. The names are tight implicitely by plotly
            _ax = "y" if i == 0 else "y{}".format(i)
            print(_ax)
            print(values[name][:10])
            fig.add_trace(go.Scatter(
                x=times, y=values[name], yaxis=_ax,
                name="{} in {}".format(name, units[name])))

            if i > 0:
                _n = "yaxis{}".format(i)
                yaxes_props[_n] = {
                    "titlefont": {"color": ax_colors[i - 1]},
                    "tickfont": {"color": ax_colors[i - 1]},
                    "overlaying": "y",
                    "side": "right",
                }
                if i == 1:
                    yaxes_props[_n]["anchor"] = "x"
                else:
                    yaxes_props[_n]["anchor"] = "free"
                    yaxes_props[_n]["position"] = 1. - (i - 1) * _offset

        # Create axis objects
        print([0, 1 - domain_cuts])
        print(yaxes_props)
        fig.update_layout(xaxis={"domain": [0, 1 - domain_cuts]}, **yaxes_props)
    else:
        # Empty figure with text that no data is there
        fig.add_annotation(
            x=0, y=0, text="No data in FIT file", showarrow=False)

    return fig
