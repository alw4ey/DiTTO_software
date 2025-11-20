DESC = '''
Grid-level distribution of farms.

By: AA
'''

import argparse
from aadata import loader
from aaviz import plot
import geopandas as gpd
from matplotlib.colors import LogNorm
#import matplotlib.pylab as plt
# from matplotlib.patches import Patch, Circle
import numpy as np
import pandas as pd
from pdb import set_trace

def farms(state, county, livestock, data, glw, county_shape, outfile):
    title = f'{livestock}, {county.capitalize()}, {state.capitalize()}'
    title = ''
    radius = {'large': 500, 'medium': 180, 'small': 30}

    if livestock == 'cattle': 
        data.loc[data.size_max<100, 'cat'] = 'small'
        data.loc[(data.size_min>=100) & (data.size_min<500), 'cat'] = 'medium'
        data.loc[data.size_min>=500, 'cat'] = 'large'
    else:
        data.loc[data.size_max<100, 'cat'] = 'small'
        data.loc[data.size_max<500, 'cat'] = 'medium'
        data.loc[data.size_max>=500, 'cat'] = 'large'

    df = data[['x', 'y', 'cat', 'farms', 'heads']].groupby(
            ['x', 'y', 'cat']).sum().reset_index()

    glw.geometry = glw.geometry.centroid
    gdf = glw[['x', 'y', 'geometry']].merge(df, on=['x', 'y'])
    gdf = gdf[~gdf.farms.isnull()]

    fig, gs = plot.initiate_figure(x=10, y=10, gs_nrows=1, gs_ncols=1,
                                   color='tableau10')

    ax = plot.subplot(fig=fig, grid=gs[0,0], func='gpd.boundary.plot', 
                      data=county_shape,
                      pf_facecolor='white', pf_edgecolor='gray',
                      la_title=title,
                      la_xlabel='', la_ylabel=''
                      )

    norm = LogNorm(vmin=gdf.heads.min(), vmax=gdf.heads.max())

    for cat in ['large', 'medium', 'small']:

        gdfc = gdf[gdf.cat==cat]
        if not gdfc.shape[0]:
            continue

        if cat=='large':
            legend = True
        else:
            legend = False

        ax = plot.subplot(fig=fig, ax=ax, func='gpd.plot',
                          data=gdfc,
                          pf_column='heads',
                          pf_alpha=.9, pf_edgecolor='black',
                          pf_legend=legend, 
                          pf_legend_kwds={'shrink': 0.5, 
                                          'label': 'Heads',
                                          'orientation': 'horizontal'},
                          pf_norm=norm,
                          pf_cmap='BuPu',
                          pf_markersize=radius[cat],
                          la_xlabel='', la_ylabel=''
                          )

    plot.savefig(outfile)

def density(state, county, livestock, data, glw, county_shape, outfile,
          color='viridis'):

    title = ''

    gdf = glw[['x', 'y', 'geometry']].merge(data, on=['x', 'y'])
    gdf = gdf[~gdf.farms.isnull()]

    fig, gs = plot.initiate_figure(x=10, y=10, gs_nrows=1, gs_ncols=1,
                                   color='tableau10')

    ax = plot.subplot(fig=fig, grid=gs[0,0], func='gpd.boundary.plot', 
                      data=county_shape,
                      pf_facecolor='white', pf_edgecolor='gray',
                      la_title=title,
                      la_xlabel='', la_ylabel=''
                      )

    norm = LogNorm(vmin=gdf.heads.min(), vmax=gdf.heads.max())

    ax = plot.subplot(fig=fig, ax=ax, func='gpd.plot',
                      data=gdf,
                      pf_column='heads',
                      pf_legend=True, 
                      pf_legend_kwds={'shrink': 0.5, 
                                      'label': 'Heads',
                                      'orientation': 'horizontal'},
                      pf_norm=norm,
                      pf_cmap=color,
                      la_xlabel='', la_ylabel=''
                      )

    plot.savefig(outfile)

if __name__ == '__main__':
    # parser
    parser=argparse.ArgumentParser(description=DESC,
            formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-s', '--state', required=True, help="Lower case")
    parser.add_argument('-c', '--county', required=True, help="Lower case")
    parser.add_argument('-l', '--livestock', required=True, help="Lower case")
    parser.add_argument('-m', '--mode', required=True, 
                        help="farms/heads/birds")
    parser.add_argument('-d', '--data_column', default='heads')
    parser.add_argument('-o', '--out_file', default='out.pdf', help="Outfile name")
    parser.add_argument('-p', '--palette', default='iridium', help="Colors for plot")
    args = parser.parse_args()

    # Load data and process it
    fips = loader.load('usa_counties')
    counties = loader.load('usa_county_shapes')
    counties = counties.astype({'statefp': 'int', 'countyfp': 'int'})

    sfp, cfp = fips[(fips.county==args.county) & 
                    (fips.state==args.state)][['statefp', 'countyfp']].values[0]
    county = counties[(counties.statefp==sfp) & (counties.countyfp==cfp)]
    glw = gpd.read_file('../../data/glw/glw_cells.shp.zip')
    glw = glw[(glw.statefp==sfp) & (glw.countyfp==cfp)]

    if args.mode == 'farms':
        data = pd.read_csv('../results/farms_to_cells.csv.zip')
        data = data[(data.statefp==sfp) & (data.countyfp==cfp) & 
                    (data.livestock==args.livestock)]
        farms(args.state, args.county, args.livestock, data, glw, county, args.out_file)
    elif args.mode == 'birds':
        data = pd.read_csv('../results/farms_to_cells.csv.zip')
        data = data[(data.statefp==sfp) & (data.countyfp==cfp) & 
                    (data.livestock==args.livestock)]
        density(args.state, args.county, args.livestock, data, glw, county, 
              args.out_file, color='viridis')
    elif args.mode == 'risk':
        data = pd.read_csv('../results/farms_to_cells.csv.zip')
        data = data[(data.statefp==sfp) & (data.countyfp==cfp) & 
                    (data.livestock==args.livestock)]
        density(args.state, args.county, args.livestock, data, glw, county, 
              args.out_file, color='YlOrRd')
