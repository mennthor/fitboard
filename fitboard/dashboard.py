"""
This is our dashboard app, now being created into the Flask server instead of
being a standalone app.
For this reason we need to put it all into an init function which is imported
into the main Flask `init_app` method.
"""

import os
from glob import glob

import numpy as np

import dash
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import dash_html_components as html
import plotly.graph_objects as go

from .ui_elements import (
    get_ui_card_form_group_select_folder,
    get_ui_card_form_group_select_fit_file,
    get_ui_graph_main,
    get_ui_card_form_group_graph_data_selector
    )
# from .ui_elements import (
#     get_ui_card_form_group_select_folder,
#     get_ui_card_form_group_select_fit_file,
#     get_ui_graph_main,
#     get_ui_card_form_group_graph_data_selector
#     )

import fitdecode


# These needs to be replaced with a proper multiuser cache if used for more
# than one user locally
_FIT_FILE_PATHS = os.path.expanduser(
        os.path.join("~", "Documents", "Zwift", "Activities"))
_FIT_FILE_LIST = []
_FIT_FILE_LIST_FILTERED = []
_FIT_FILE_SIZES = []
_CUR_FIT_FILES = []
_CUR_VALUES = {}
_CUR_UNITS = {}
_EMPTY_FIT_SIZE = 584  # In bytes


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

    # Just use a global variable here, only OK for one single user
    global _FIT_FILE_LIST, _FIT_FILE_SIZES
    global _FIT_FILE_LIST_FILTERED, _CUR_FIT_FILES
    _FIT_FILE_LIST, _FIT_FILE_SIZES = _init_fit_file_db(_FIT_FILE_PATHS)
    _FIT_FILE_LIST_FILTERED = [
        fname for fname, fs in zip(_FIT_FILE_LIST, _FIT_FILE_SIZES)
        if fs > _EMPTY_FIT_SIZE
    ]
    _CUR_FIT_FILES = _FIT_FILE_LIST_FILTERED

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
    card_path_selector = get_ui_card_form_group_select_folder(
        "group_select_folder_")
    card_fit_file_selector = get_ui_card_form_group_select_fit_file(
        "fit_file_selector_", _CUR_FIT_FILES)
    card_graph_dataset_selector_ = get_ui_card_form_group_graph_data_selector(
        "graph_dataset_selector_")
    card_graph_main = get_ui_graph_main("graph_main_")

    dash_app.layout = dbc.Container(
        [
            html.H2("Viewer Board for FIT Data", style={"margin-top": 5}),
            dbc.Row(
                [
                    dbc.Col(card_path_selector),
                    dbc.Col(card_fit_file_selector),
                ],
                style={"margin-top": "10px"}
            ),
            dbc.Row(
                [
                    dbc.Col(card_graph_dataset_selector_),
                ],
                style={"margin-top": "10px"}
            ),
            dbc.Row(
                [
                    dbc.Col(card_graph_main),
                ],
                style={"margin-top": "10px"}
            ),
        ],
        fluid=False,
    )


def _init_callbacks(dash_app):
    """
    Init our dashboard callbacks, this defines the board's functionality.
    """
    # Callback for all main graph controls.
    # Note: You can only have one callback output for each element globally, so
    # all functionality altering the graph must be in this callback here.
    # Note: The relayout data input has the drawback, that the interactive
    # scaling on the y axis is now not working anymore, don't really know why.
    @dash_app.callback(
        [Output("fit_file_selector_div", "children"),
         Output("graph_main_graph", "figure"),
         Output("graph_main_alert", "children"),
         Output("graph_main_div_graph", "style"),
         Output("graph_main_div_alert", "style"),
         Output("graph_dataset_selector_div", "children")],
        [Input("fit_file_selector_dropdown", "value"),
         Input("graph_dataset_selector_checklist", "value"),
         Input("graph_dataset_selector_checklist_mean", "value"),
         Input("graph_main_graph", "relayoutData")])
    def cb_fig_control(dropdown_val, ynames, plot_means, clickdata):
        # Read the date from selected file, make figure, convert to base64 and
        # feed into html.img tag. If err, display the error instead
        print("In cb_dropdown_dataset")
        print("  - dopdown val is: {}".format(dropdown_val))
        print("  - switch vals are: {}".format(ynames))
        ga_text = ""
        dg_style = {"display": "block"}
        dga_style = {"display": "none"}
        try:
            global _CUR_VALUES, _CUR_UNITS
            _CUR_VALUES, _CUR_UNITS = _load_fit_file(dropdown_val)
            plot_means = True if plot_means else False  # List to bool convers.
            try:
                xrnge = [
                    clickdata["xaxis.range[0]"],
                    clickdata["xaxis.range[1]"],
                ]
            except KeyError:
                xrnge = [None, None]
            print("xrnge : ", xrnge)
            fig = _make_figure(
                _CUR_VALUES, _CUR_UNITS,
                ynames=ynames, xrnge=xrnge, plot_means=plot_means)
        except IOError as err:
            fig = go.Figure()  # Dummy, will be hidden anyway
            ga_text = str(err)
            # Switch visibility
            dg_style, dga_style = dga_style, dg_style
            dga_style["margin"] = "auto"

        # The feedback message under the dropdown
        msg = ("Selected '{}'".format(dropdown_val)
               if dropdown_val is not None else "No dataset selected",)
        return msg, fig, ga_text, dg_style, dga_style, (", ".join(ynames),)

    @dash_app.callback(
        [Output("fit_file_selector_dropdown", "options"),
         Output("fit_file_selector_dropdown", "placeholder"),
         Output("fit_file_selector_dropdown", "value"),
         Output("fit_file_selector_label", "children")],
        [Input("fit_file_selector_checklist", "value")]
    )
    def cb_dropdown_switches_ignore(switch_val):
        print("In cb_dropdown_switches_ignore")
        print("  - switch_val is: {}".format(switch_val))
        global _CUR_FIT_FILES
        if switch_val:  # This is actually a check on len(list) > 0
            _CUR_FIT_FILES = _FIT_FILE_LIST_FILTERED
            msg = "Select Dataset (non-empty)"
        else:
            _CUR_FIT_FILES = _FIT_FILE_LIST
            msg = "Select Dataset (all)"

        # Update fit file selector dropwdown
        opts = [{"label": os.path.basename(fname), "value": fname}
                for fname in _CUR_FIT_FILES]
        placeholder = os.path.basename(
            _CUR_FIT_FILES[-1]) if _CUR_FIT_FILES else ""
        value = _CUR_FIT_FILES[-1] if _CUR_FIT_FILES else None
        print("  - placeholder is set to {}".format(placeholder))
        print("  - value is set to {}".format(value))
        return opts, placeholder, value, msg


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
    file_sizes = [os.path.getsize(f) for f in fit_files]
    return fit_files, file_sizes


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

    return values, units


def _make_figure(values, units, ynames=["power"],
                 xrnge=[None, None], plot_means=True):
    fig = go.Figure()

    print("In _make_figure")
    print("ynames", ynames)
    print("xrnge", xrnge)
    print("plot_means", plot_means)

    if values:
        ax_colors = {
            "power": "#353132",
            "speed_kmh": "#2ca02c",
            "cadence": "#1f77b4",
            "altitude_norm": "#7f7f7f",
            "heart_rate": "#2ca02c",
            }
        # Time in minutes
        times = np.array(values["time_norm"]) / 60.

        # Slice it?
        idx0, idx1 = 0, -1
        if xrnge[0] is not None:
            idx0 = np.where(times > xrnge[0])[0][0]
        if xrnge[1] is not None:
            idx1 = np.where(times < xrnge[1])[0][-1]
        times = times[idx0:idx1]

        # We need to make room for all the potential extra axes
        _offset = 0.1
        _offsets = [1. - j * _offset for j in range(len(ynames) - 2, 0, -1)]
        domain_cuts = max(0, (len(ynames) - 1) * _offset)

        # Plot each name's data set
        _title = []
        yaxes_props = {}
        for i, name in enumerate(ynames):
            # First value is drawn to the left main axis, all others are getting
            # a new axis on the right. The names are tight implicitely by plotly
            _ax_id = "y" if i == 0 else "y{}".format(i + 1)
            _ax_name = "yaxis" if i == 0 else "yaxis{}".format(i + 1)

            print("Plot {} on axis {} ({}, {})".format(name, i, _ax_id, _ax_name))
            fig.add_trace(go.Scatter(
                x=times, y=values[name][idx0:idx1], yaxis=_ax_id,
                name=name,
                line={"color": ax_colors[name]}, showlegend=False,
                mode="lines",
            ))

            if plot_means:
                _mean = np.mean(values[name][idx0:idx1])
                fig.add_trace(go.Scatter(
                    x=[times[0], times[-1]], y=2 * [_mean],
                    yaxis=_ax_id, name=name,
                    line={"color": ax_colors[name], "dash": "dash"},
                    mode="lines",
                    showlegend=False,
                ))
                _title.append("{}={:.1f}".format(name, _mean))

            yaxes_props[_ax_name] = {
                "titlefont": {"color": ax_colors[name]},
                "tickfont": {"color": ax_colors[name]},
            }

            if i > 0:
                yaxes_props[_ax_name]["overlaying"] = "y"
                yaxes_props[_ax_name]["side"] = "right"
                yaxes_props[_ax_name]["showgrid"] = False
                if i == 1:
                    yaxes_props[_ax_name]["anchor"] = "x"
                else:
                    yaxes_props[_ax_name]["anchor"] = "free"
                    yaxes_props[_ax_name]["position"] = _offsets[i - 2]
            yaxes_props[_ax_name]["title"] = "{} in {}".format(
                name, units[name])

        # Create axis objects
        print("Domain cut: ", [0, 1 - domain_cuts])
        print(yaxes_props)
        fig.update_layout(
            xaxis={"domain": [0, 1 - domain_cuts]}, **yaxes_props,
            xaxis_range=xrnge,
            width=1000 * 1. / (1 - domain_cuts),
            title={"text": "Mean values: " + ", ".join(_title)} if _title else None
        )
    else:
        # Empty figure with text that no data is there
        fig.add_annotation(
            x=0, y=0, text="No data to plot", showarrow=False)

    return fig


if __name__ == "__main__":
    dash_app = dash.Dash(
        external_stylesheets=[dbc.themes.MINTY],
    )

    # Just use a global variable here, only OK for one single user
    _FIT_FILE_LIST, _FIT_FILE_SIZES = _init_fit_file_db(_FIT_FILE_PATHS)
    _FIT_FILE_LIST_FILTERED = [
        fname for fname, fs in zip(_FIT_FILE_LIST, _FIT_FILE_SIZES)
        if fs > _EMPTY_FIT_SIZE
    ]
    _CUR_FIT_FILES = _FIT_FILE_LIST_FILTERED

    # Build the dashboard layout
    _init_layout(dash_app)

    # Init callbacks on Flask app load, not globally before it is running
    _init_callbacks(dash_app)

    print("Dash app created")

    dash_app.run_server(debug=True)
