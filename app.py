import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, ctx
from dash.dependencies import Input, Output, State
import requests
import difflib
from unidecode import unidecode

# ----------------------------
# 1) Dados
# ----------------------------
DF = pd.read_csv("votos.csv", sep=";")  # colunas: Inspetoria, Cidade, Votos
DF["Cidade"] = DF["Cidade"].astype(str).str.strip()
DF["Inspetoria"] = DF["Inspetoria"].astype(str).str.strip()

GEOJSON_URL = "https://raw.githubusercontent.com/tbrugz/geodata-br/master/geojson/geojs-42-mun.json"
GEO = requests.get(GEOJSON_URL).json()

# Conjunto de nomes oficiais do GeoJSON
GEO_NAMES = sorted({f["properties"]["name"].strip() for f in GEO["features"]})
GEO_NAMES_NORMALIZED = {unidecode(n).lower(): n for n in GEO_NAMES}  # mapa normalizado->oficial

# ----------------------------
# 2) App (layout)
# ----------------------------
app = Dash(__name__)
app.title = "CREA-SC | Eleição 2022"

def kpi_card(title, id_value):
    return html.Div(
        style={"padding":"12px 16px","border":"1px solid #e5e7eb",
               "borderRadius":"10px","boxShadow":"0 1px 6px rgba(0,0,0,.06)","background":"#fff"},
        children=[
            html.Div(title, style={"fontSize":"13px","color":"#6b7280","marginBottom":"6px"}),
            html.Div(id=id_value, style={"fontSize":"22px","fontWeight":700})
        ]
    )

app.layout = html.Div(
    style={"display":"grid","gridTemplateColumns":"300px 1fr","gap":"16px","padding":"16px",
           "fontFamily":"system-ui, -apple-system, Segoe UI, Roboto"},
    children=[
        # -------- Sidebar --------
        html.Div(
            style={"display":"flex","flexDirection":"column","gap":"12px",
                   "position":"sticky","top":"16px","alignSelf":"start"},
            children=[
                html.H2("Mapa de Votos CREA-SC", style={"margin":"0 0 6px 0"}),
                html.Div("Filtros", style={"color":"#6b7280","fontSize":"12px","marginBottom":"4px"}),

                dcc.Dropdown(
                    id="filtro_inspetoria",
                    options=[{"label": i, "value": i} for i in sorted(DF["Inspetoria"].unique())],
                    value=None,
                    placeholder="Escolha uma inspetoria",
                    clearable=True
                ),
                dcc.Dropdown(
                    id="filtro_cidade",
                    options=[{"label": c, "value": c} for c in sorted(DF["Cidade"].unique())],
                    value=None,
                    placeholder="Busque um município",
                    clearable=True,
                    searchable=True
                ),
                html.Button("Limpar filtros", id="btn_clear", n_clicks=0,
                            style={"padding":"10px 12px","border":"1px solid #d1d5db",
                                   "borderRadius":"8px","background":"#f9fafb","cursor":"pointer"}),

                html.Hr(),
                html.Div("Indicadores", style={"color":"#6b7280","fontSize":"12px","marginBottom":"4px"}),
                html.Div(
                    style={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"10px"},
                    children=[
                        kpi_card("Total de votos (filtro)", "kpi_total_votos"),
                        kpi_card("Municípios no filtro", "kpi_qtd_muns"),
                    ]
                ),

                html.Hr(),
                html.Div("Diagnóstico de correspondência", style={"color":"#6b7280","fontSize":"12px","marginBottom":"6px"}),
                html.Button("Verificar correspondências", id="btn_match", n_clicks=0,
                            style={"padding":"10px 12px","border":"1px solid #d1d5db",
                                   "borderRadius":"8px","background":"#f9fafb","cursor":"pointer","marginBottom":"8px"}),
                html.Button("Baixar diagnóstico (CSV)", id="btn_download", n_clicks=0,
                            style={"padding":"10px 12px","border":"1px solid #d1d5db",
                                   "borderRadius":"8px","background":"#f9fafb","cursor":"pointer","marginBottom":"8px"}),
                dcc.Download(id="download_diag"),
                html.Div(id="diag_area", style={"maxHeight":"28vh","overflowY":"auto","fontSize":"13px"})
            ]
        ),

        # -------- Conteúdo principal --------
        html.Div(
            style={"display":"grid","gridTemplateRows":"minmax(420px, 56vh) 1fr","gap":"16px"},
            children=[
                dcc.Graph(id="mapa", style={"height":"100%"}),
                html.Div(
                    children=[
                        html.H3("Ranking de votos por município (no filtro)", style={"margin":"0 0 8px 0"}),
                        dcc.Graph(id="ranking", style={"height":"44vh"})
                    ]
                )
            ]
        )
    ]
)

# ----------------------------
# Utilitário p/ centro do polígono (quando não há bbox)
# ----------------------------
def _centro_feature(feature):
    geom = feature["geometry"]
    coords = []
    if geom["type"] == "Polygon":
        coords = geom["coordinates"][0]
    elif geom["type"] == "MultiPolygon":
        coords = max(geom["coordinates"], key=lambda poly: len(poly[0]))[0]
    if not coords:
        return None, None
    lons = [p[0] for p in coords]
    lats = [p[1] for p in coords]
    return sum(lats)/len(lats), sum(lons)/len(lons)

# ----------------------------
# 3) Callbacks
# ----------------------------

# (1) Limpar apenas a inspetoria (evita duplicidade de outputs com filtro_cidade.value)
@app.callback(
    Output("filtro_inspetoria", "value"),
    Input("btn_clear", "n_clicks"),
    prevent_initial_call=True
)
def clear_filters(n):
    return None

# (2) Atualizar opções do dropdown de Cidades + limpar cidade quando necessário
@app.callback(
    Output("filtro_cidade", "options"),
    Output("filtro_cidade", "value"),
    Input("filtro_inspetoria", "value"),
    Input("btn_clear", "n_clicks"),
    State("filtro_cidade", "value")
)
def atualizar_opcoes_cidade(inspetoria, n_clear, cidade_atual):
    # lista de cidades conforme a inspetoria
    if inspetoria:
        cidades = (DF.loc[DF["Inspetoria"] == inspetoria, "Cidade"]
                     .dropna().drop_duplicates().sort_values().tolist())
    else:
        cidades = DF["Cidade"].dropna().drop_duplicates().sort_values().tolist()

    options = [{"label": c, "value": c} for c in cidades]

    # Se clicou no botão "Limpar filtros", zera a cidade
    if ctx.triggered_id == "btn_clear":
        cidade_atual = None
    # Se a cidade atual não pertence mais à lista filtrada, limpa também
    elif cidade_atual not in cidades:
        cidade_atual = None

    return options, cidade_atual

# (3) Atualizar mapa, ranking e KPIs
@app.callback(
    Output("mapa", "figure"),
    Output("ranking", "figure"),
    Output("kpi_total_votos", "children"),
    Output("kpi_qtd_muns", "children"),
    Input("filtro_inspetoria", "value"),
    Input("filtro_cidade", "value"),
)
def atualizar_visuais(inspetoria, cidade):
    df = DF.copy()
    if inspetoria:
        df = df[df["Inspetoria"] == inspetoria]
    if cidade:
        df = df[df["Cidade"] == cidade]

    total_votos = int(df["Votos"].sum()) if not df.empty else 0
    qtd_muns = int(df["Cidade"].nunique()) if not df.empty else 0

    # Mapa base
    fig_map = px.choropleth_mapbox(
        df,
        geojson=GEO,
        locations="Cidade",
        featureidkey="properties.name",
        color="Votos",
        color_continuous_scale="Blues",
        hover_name="Cidade",
        hover_data={"Inspetoria": True, "Votos": True, "Cidade": False},
        mapbox_style="open-street-map",  # sem token
        center={"lat": -27.2423, "lon": -50.2189},
        zoom=6,
    )
    fig_map.update_traces(marker_line_width=0.6, marker_line_color="#555",
                          selector=dict(type="choroplethmapbox"))
    fig_map.update_layout(margin=dict(l=0, r=0, t=0, b=0),
                          coloraxis_colorbar=dict(title="Votos"))

    # Destaque/zoom em cidade
    if cidade:
        for f in GEO["features"]:
            if f["properties"]["name"] == cidade:
                destaque = px.choropleth_mapbox(
                    pd.DataFrame({"Cidade":[cidade]}),
                    geojson={"type":"FeatureCollection","features":[f]},
                    locations="Cidade",
                    featureidkey="properties.name",
                    opacity=0
                ).data[0]
                destaque.marker.line.width = 5
                destaque.marker.line.color = "red"
                fig_map.add_trace(destaque)

                if "bbox" in f:
                    minx, miny, maxx, maxy = f["bbox"]
                    center_lat = (miny + maxy) / 2
                    center_lon = (minx + maxx) / 2
                else:
                    center_lat, center_lon = _centro_feature(f)
                if center_lat and center_lon:
                    fig_map.update_layout(mapbox_center={"lat": center_lat, "lon": center_lon},
                                          mapbox_zoom=8)
                break

    # Ranking
    df_rank = df.groupby("Cidade", as_index=False)["Votos"].sum() \
                .sort_values("Votos", ascending=False).head(15)
    fig_rank = px.bar(df_rank, x="Votos", y="Cidade", orientation="h", text="Votos")
    fig_rank.update_traces(textposition="outside", cliponaxis=False)
    fig_rank.update_layout(margin=dict(l=0, r=0, t=0, b=0),
                           yaxis=dict(autorange="reversed"))

    return (fig_map,
            fig_rank,
            f"{total_votos:,}".replace(",", "."),
            f"{qtd_muns}")

# (4) Diagnóstico de correspondência (renderizado na tela)
@app.callback(
    Output("diag_area", "children"),
    Input("btn_match", "n_clicks"),
    prevent_initial_call=True
)
def diagnosticar(n_clicks):
    csv_cidades = sorted({c.strip() for c in DF["Cidade"].dropna().astype(str)})
    linhas = []
    for c in csv_cidades:
        if c in GEO_NAMES:
            continue
        key = unidecode(c).lower()
        sugerida = GEO_NAMES_NORMALIZED.get(key)
        if not sugerida:
            sugestoes = difflib.get_close_matches(c, GEO_NAMES, n=1, cutoff=0.75)
            sugerida = sugestoes[0] if sugestoes else ""
        linhas.append((c, sugerida))

    if not linhas:
        return html.Div("Tudo certo! Todos os municípios do CSV batem com o GeoJSON. ✅",
                        style={"color":"#065f46"})

    header = html.Tr([html.Th("Município no CSV"), html.Th("Sugestão (GeoJSON)")])
    rows = [html.Tr([html.Td(a), html.Td(b if b else "—")]) for a, b in linhas]
    return html.Table([header] + rows,
                      style={"width":"100%","borderCollapse":"collapse"},
                      className="diag-table")

# (5) Download do diagnóstico em CSV
@app.callback(
    Output("download_diag", "data"),
    Input("btn_download", "n_clicks"),
    prevent_initial_call=True
)
def baixar_diagnostico(n_clicks):
    csv_cidades = sorted({c.strip() for c in DF["Cidade"].dropna().astype(str)})
    rows = []
    for c in csv_cidades:
        if c in GEO_NAMES:
            continue
        key = unidecode(c).lower()
        sugerida = GEO_NAMES_NORMALIZED.get(key)
        if not sugerida:
            sugestoes = difflib.get_close_matches(c, GEO_NAMES, n=1, cutoff=0.75)
            sugerida = sugestoes[0] if sugestoes else ""
        rows.append({"municipio_csv": c, "sugestao_geojson": sugerida})

    if not rows:
        rows = [{"municipio_csv": "(todos conferem)", "sugestao_geojson": ""}]

    df_out = pd.DataFrame(rows)
    return dcc.send_data_frame(df_out.to_csv, "diagnostico_municipios.csv", index=False)

# ----------------------------
# 4) Run
# ----------------------------
if __name__ == "__main__":
    app.run(debug=True)
