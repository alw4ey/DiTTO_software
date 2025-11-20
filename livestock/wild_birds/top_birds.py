import argparse
from aadata import loader
from aautils import geometry
from aaviz import plot
import geopandas as gpd
import json
import matplotlib.cm as cm
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.colors import LogNorm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pdb import set_trace
import pydeck as pdk
from shapely.geometry import mapping, Polygon, MultiPolygon
from shapely.ops import unary_union

from livestock_3d import *

# Load data and process it
states = loader.load('usa_state_shapes')
states = states[~states.name.isin(['alaska', 'hawaii', 'puerto rico', 
                                   'guam',
                                   'commonwealth of the northern mariana islands',
                                   'united states virgin islands',
                                   'american samoa'
                                   ])]

country_geom = unary_union(states.geometry)
dates = ['2022-01-04', '2022-04-05', '2022-07-05', '2022-10-04']
species = ['mallar3', 'snogoo', 'cangoo']
data = pd.read_parquet('../../../../data/ldt/birds.parquet')
data = data[data.date.isin(dates)]
data = data[data.species.isin(species)].reset_index(drop=True)
data[['lon', 'lat']] = geometry.glw_to_lonlat(data.x, data.y)
data['geometry'] = geometry.coords_to_geom(data.lon, data.lat)
data = gpd.GeoDataFrame(data)
poly = gpd.GeoDataFrame(index=[0], crs=data.crs, 
                        geometry=[country_geom])
data = gpd.overlay(data, poly, how='intersection')
data.to_file(filename='top_birds.shp', driver='ESRI Shapefile')


