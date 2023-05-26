"""
Outsourced UI element blobs.
"""

import os

import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objects as go


def get_ui_card_form_group_select_folder(id_pref):
    """
    Return a `dash_bootstrap_components.Card` with a `dash_bootstrap_components`
    form group including radio items and text input and outside the form group a
    `dash_html_components.Div` for text output.
    These can be accessed using the created ids 'radio_items', 'input',
    'div_alert', each prepended with `id_pref`.
    """
    return dbc.Card(
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
                        id=id_pref + "radio_items",
                    ),
                    dbc.Input(
                        id=id_pref + "input",
                        placeholder="Enter custom path",
                        type="text"
                    ),
                ]
            ),
            # Hidden, except users enter invalid path, then it show with err msg
            html.Div(
                [
                    dbc.Alert("", id=id_pref + "alert", color="danger"),
                ],
                id=id_pref + "div_alert",
                style={"display": "none"}
            ),
        ],
        body=True,
        color="light",
    )


def get_ui_card_form_group_select_fit_file(id_pref, fit_files):
    """
    Return a `dash_bootstrap_components.Card` with a `dash_bootstrap_components`
    form group including a text label, dropwdown list and a checklist and
    outside the form group a `dash_html_components.Div` for text output.
    These can be accessed using the created ids 'label', 'dropdown',
    'checklist', 'div' each prepended with `id_pref`.

    `fit_files` is a list of default list items to show in the dropwdown menu.
    """
    return dbc.Card(
        [
            dbc.FormGroup(
                [
                    dbc.Label("Select Dataset", id=id_pref + "label"),
                    dcc.Dropdown(
                        id=id_pref + "dropdown",
                        options=[{"label": os.path.basename(fname), "value": fname}
                                 for fname in fit_files],
                        placeholder=os.path.basename(fit_files[-1]) if fit_files else "",
                        value=fit_files[-1] if fit_files else None,
                    ),
                    html.Br(),
                    dbc.Checklist(
                        options=[
                            {"label": "Ignore empty files", "value": "true"},
                        ],
                        value=["true"],
                        id=id_pref + "checklist",
                        switch=True,
                        inline=True,
                    ),
                ]
            ),
            html.Div(id=id_pref + "div"),
        ],
        body=True,
        color="light",
    )


def get_ui_card_form_group_graph_data_selector(id_pref):
    """
    Return a `dash_bootstrap_components.Card` with a `dash_bootstrap_components`
    form group including a checklist and
    outside the form group a `dash_html_components.Div` for text output.
    These can be accessed using the created ids 'checklist', 'checklist_mean'
    and 'div', each prepended with `id_pref`.
    """
    return dbc.Card(
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
                            {"label": "Heart Rate", "value": "heart_rate"},
                        ],
                        value=["power"],
                        id=id_pref + "checklist",
                        switch=True,
                        inline=True,
                    ),
                    dbc.Checklist(
                        options=[
                            {"label": "Show mean value in selected range", "value": "true"},
                        ],
                        value=["true"],
                        id=id_pref + "checklist_mean",
                        switch=True,
                        inline=True,
                    ),
                ]
            ),
            html.Div(id=id_pref + "div"),
        ],
        body=True,
        color="light",
    )


def get_ui_graph_main(id_pref):
    """
    Return a `dash_html_components.Div` with two inner
    `dash_html_components.Div`.
    The first div holds a `dash_html_components.Graph`, the second one a
    `dash_bootstrap_components.Alert` box which is hidden by default
    (`style={"display": "none"}`).
    These can be accessed using the created ids 'graph', 'alert', 'div_graph',
    'div_alert' and 'div'.
    """
    # Main graph showing the loaded FIT file, centered below card row.
    # The divs are switched on/off via the style element. Instead of the graph,
    # an alert box is displayed when the fit file is faulty and vice-versa
    return html.Div(
        [
            html.Div(
                [
                    dbc.Card(
                        [
                            dcc.Graph(figure=go.Figure(), id=id_pref + "graph"),
                        ],
                        body=True,
                        color="light",
                    ),
                ],
                id=id_pref + "div_graph",
                style={"display": "block"},
            ),
            html.Div(
                [
                    dbc.Card(
                        [
                            dbc.Alert("", id=id_pref + "alert", color="danger"),
                        ],
                        body=True,
                        color="light",
                    ),
                ],
                id=id_pref + "div_alert",
                style={"display": "none"}
            ),
        ],
        id=id_pref + "div"
    )
