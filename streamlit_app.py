import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import xml.etree.ElementTree as ET
import pandas as pd


st.set_page_config(
    page_title="Geospatial Mapping of the Canadian Financial Sector for Physical Risk Assessment",
    layout="wide"
)

st.title("Geospatial Mapping of the Canadian Financial Sector for Physical Risk Assessment")


st.markdown(
    """
    This dashboard combines [NASA’s Global Imagery Browse Services (GIBS)](https://nasa-gibs.github.io/gibs-api-docs/) with
    geocoded locations of [Canadian Banks](https://github.com/Aryamik/Geocoded-Addresses-of-Canadian-Financial-Institutions) that has been sourced from Payments Canada; enabling a real time assessment of physical risks of climate change. This application uses imagery provided by services from NASA's Global Imagery Browse Services (GIBS), part of NASA's Earth Science Data and Information System (ESDIS).

    """
)

st.markdown(
    """
   **Disclaimer:** This application is provided for informational and research purposes only. While care has been taken to compile the data accurately, no guarantees are made regarding completeness, accuracy, or timeliness of the data.
    """
)


# Setting up the base layer from NASA's Global Imagery Browse Services (GIBS) system

WMS_BASE_URL = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
CAPABILITIES_URL = f"{WMS_BASE_URL}?SERVICE=WMS&REQUEST=GetCapabilities"

NS = {
    "wms": "http://www.opengis.net/wms",
    "xlink": "http://www.w3.org/1999/xlink",
}

# WMS capabilities parsing

@st.cache_data(show_spinner=True)
def load_wms_hierarchy():
    r = requests.get(CAPABILITIES_URL)
    r.raise_for_status()

    root = ET.fromstring(r.content)
    top_layer = root.find("wms:Capability/wms:Layer", NS)

    def collect_layers(layer):
        out = []
        name = layer.find("wms:Name", NS)
        title = layer.find("wms:Title", NS)

        if name is not None:
            out.append({
                "name": name.text,
                "title": title.text if title is not None else name.text
            })

        for child in layer.findall("wms:Layer", NS):
            out.extend(collect_layers(child))

        return out

    hierarchy = {}

    for category in top_layer.findall("wms:Layer", NS):
        cat_title_el = category.find("wms:Title", NS)
        if cat_title_el is None:
            continue

        subcats = {}
        for subcat in category.findall("wms:Layer", NS):
            sub_title_el = subcat.find("wms:Title", NS)
            if sub_title_el is None:
                continue

            layers = collect_layers(subcat)
            if layers:
                subcats[sub_title_el.text] = layers

        if subcats:
            hierarchy[cat_title_el.text] = subcats

    return hierarchy


wms_hierarchy = load_wms_hierarchy()

# Creating a dropdown option for selecting categories
category = st.selectbox("Category", sorted(wms_hierarchy))
subcategory = st.selectbox(
    "Sub-category",
    sorted(wms_hierarchy[category])
)

layers = wms_hierarchy[category][subcategory]

if len(layers) == 1:
    layer_title = layers[0]["title"]
    layer_name = layers[0]["name"]
else:
    title_to_name = {l["title"]: l["name"] for l in layers}
    layer_title = st.selectbox("Layer", sorted(title_to_name))
    layer_name = title_to_name[layer_title]

# Function for adding a legend for the selected layer
@st.cache_data(show_spinner=False)
def embedded_legend(layer_name):
    r = requests.get(CAPABILITIES_URL)
    r.raise_for_status()

    root = ET.fromstring(r.content)

    for layer in root.findall(".//wms:Layer", NS):
        name = layer.find("wms:Name", NS)
        if name is not None and name.text == layer_name:
            legend = layer.find(
                ".//wms:Style/wms:LegendURL/wms:OnlineResource", NS
            )
            if legend is not None:
                return legend.attrib.get(
                    "{http://www.w3.org/1999/xlink}href"
                )
    return None


def fallback_legend(layer):
    return (
        f"{WMS_BASE_URL}"
        "?SERVICE=WMS"
        "&REQUEST=GetLegendGraphic"
        "&FORMAT=image/png"
        "&VERSION=1.3.0"
        f"&LAYER={layer}"
    )


legend_url = embedded_legend(layer_name) or fallback_legend(layer_name)

# Importing the geocoded addresses for branches of all Canadian financial institutions.
# YOu can obviously change this dataset/code below to fit your purpose. Just make sure the fields are consistent. 

banks_df = pd.read_csv("data/Canadian Banks Geocoded.csv")

with st.form("map_controls"):
    bank_filter = st.selectbox(
        "Filter by Bank Name",
        ["All"] + sorted(banks_df["bank_name"].unique())
    )

    submitted = st.form_submit_button("Submit")

if submitted:
    if bank_filter != "All":
        banks_df = banks_df[banks_df["bank_name"] == bank_filter]

    # -----------------------------
    # Map
    # -----------------------------
    m = folium.Map(location=[20, 0], zoom_start=2, tiles="OpenStreetMap")

    folium.WmsTileLayer(
        url=WMS_BASE_URL,
        name=layer_title,
        layers=layer_name,
        fmt="image/png",
        transparent=True,
        overlay=True,
        control=True,
    ).add_to(m)

    #You can modify this code or the dataset according to the fields that you have
    for _, row in banks_df.iterrows():
        folium.Marker(
            location=[row["Lat"], row["Long"]], 
            popup=(
                f"<b>{row['bank_name']}</b><br>"
                f"{row['Address']}<br>"
                f"Provider: {row['Provider']}<br>"
                f"Institution: {row['institution']}<br>"
                f"Transit: {row['transit']}<br>"
                f"Routing: {row['routing']}"
            ),
            icon=folium.Icon(color="blue", icon="bank", prefix="fa"),
        ).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    if legend_url:
        m.get_root().html.add_child(
            folium.Element(
                f"""
                <div style="
                    position: fixed;
                    bottom: 20px;
                    left: 20px;
                    z-index: 9999;
                    background: white;
                    padding: 10px;
                    border: 2px solid #777;
                    border-radius: 6px;
                    box-shadow: 2px 2px 6px rgba(0,0,0,.3);
                    max-width: 260px;
                ">
                    <b>{layer_title}</b><br>
                    <img src="{legend_url}" style="width:240px;">
                </div>
                """
            )
        )

    st_folium(m, width=1400, height=900, returned_objects=[])
else:
    st.info("Select your filters and click **Submit** to display results.")
