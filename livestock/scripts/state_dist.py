DESC = '''
Grid-level distribution of farms.

By: AA
'''

import argparse
from aadata import loader
from aaviz import plot
import geopandas as gpd
import numpy as np
import pandas as pd
from pdb import set_trace

STATE_FIPS = {
    "alabama": 1,
    "alaska": 2,
    "arizona": 4,
    "arkansas": 5,
    "california": 6,
    "colorado": 8,
    "connecticut": 9,
    "delaware": 10,
    "florida": 12,
    "georgia": 13,
    "hawaii": 15,
    "idaho": 16,
    "illinois": 17,
    "indiana": 18,
    "iowa": 19,
    "kansas": 20,
    "kentucky": 21,
    "louisiana": 22,
    "maine": 23,
    "maryland": 24,
    "massachusetts": 25,
    "michigan": 26,
    "minnesota": 27,
    "mississippi": 28,
    "missouri": 29,
    "montana": 30,
    "nebraska": 31,
    "nevada": 32,
    "new hampshire": 33,
    "new jersey": 34,
    "new mexico": 35,
    "new york": 36,
    "north carolina": 37,
    "north dakota": 38,
    "ohio": 39,
    "oklahoma": 40,
    "oregon": 41,
    "pennsylvania": 42,
    "rhode island": 44,
    "south carolina": 45,
    "south dakota": 46,
    "tennessee": 47,
    "texas": 48,
    "utah": 49,
    "vermont": 50,
    "virginia": 51,
    "washington": 53,
    "west virginia": 54,
    "wisconsin": 55,
    "wyoming": 56,
    "district of columbia": 11,
    "puerto rico": 72
}

def dist(state, glw, heads, assg, counties, stats, hspace=None,
         full=None):

    # Various choropleths
    types = assg.livestock.drop_duplicates().sort_values()
    num_types = len(types)
    if full:
        wspace=.1
    else:
        wspace=.01
    fig, gs = plot.initiate_figure(x=4*num_types, y=14, 
                                   gs_nrows=5, gs_ncols=num_types,
                                   gs_wspace=wspace, gs_hspace=hspace,
                                   color='tableau10',
                                   scilimits=[-2,2])

    for i,ty in enumerate(types):
        if not full:
            continue
        if i==0:
            ylabel = '\\parbox{4.5cm}{\\center GLW grid-level \\\\ assignment}'
        else:
            ylabel = ''
        ax = plot.subplot(fig=fig, grid=gs[2,i], func='gpd.plot', 
                          data=glw[glw.livestock==ty],
                          pf_column='val',
                          pf_legend=True, pf_legend_kwds={'shrink': 0.28},
                          la_title='',
                          la_ylabel=ylabel,
                          la_xlabel=f'{glw[glw.livestock==ty].val.sum(): .0f}'
                          )

    for i,ty in enumerate(types):
        if not full:
            continue
        if i==0:
            ylabel = '\\parbox{4.5cm}{\\center AgCensus heads \\\\ per county}'
        else:
            ylabel = ''
        if ty == 'chickens':
            cat = 'county_totals'
        else:
            cat = 'county_by_farmsize'
            xlabel = f'{heads[(heads.commodity_desc==ty) & (heads.category==cat)].value.sum(): .0f}'
        ax = plot.subplot(fig=fig, grid=gs[1,i], func='gpd.boundary.plot', 
                          data=counties,
                          pf_facecolor='white', pf_edgecolor='gray'
                          )
        ax = plot.subplot(fig=fig, ax=ax, grid=gs[1,i], func='gpd.plot', 
                          data=heads[heads.commodity_desc==ty],
                          pf_column='value',
                          pf_legend=True, pf_legend_kwds={'shrink': 0.28},
                          la_xlabel=xlabel, la_ylabel=ylabel
                          )

    for i,ty in enumerate(types):
        if i==0:
            if full:
                ylabel = '\\parbox{4cm}{\\center Our grid-level \\\\ assignment}'
                fsylabel = 'normalsize'
            else:
                ylabel = state.capitalize()
                fsylabel = 'Large'
        else:
            ylabel = ''
        if full:
            xlabel = f'{assg[assg.livestock==ty].heads.sum(): .0f}'
        else:
            xlabel = ''
        ax = plot.subplot(fig=fig, grid=gs[0,i], func='gpd.boundary.plot', 
                          data=counties,
                          pf_facecolor='white', pf_edgecolor='gray'
                          )
        ax = plot.subplot(fig=fig, ax=ax, grid=gs[2,i], func='gpd.plot', 
                          data=assg[assg.livestock==ty],
                          pf_column='heads',
                          pf_legend=True, pf_legend_kwds={'shrink': 0.28},
                          la_title=f'{ty}',
                          la_xlabel=xlabel, 
                          la_ylabel=ylabel,
                          fs_ylabel=fsylabel
                          )

    map_sc = {1: '1', 2: '2', 3.1: '3', 3.2: '3', 3.3: '3'}
    stats.scenario = stats.scenario.map(map_sc)
    stats = stats.sort_values('scenario')
    for i,ty in enumerate(types):
        if not full:
            continue
        if i==0:
            ylabel = '\\% Instances'
        else:
            ylabel = ''
        #xt_setticks=['1', '2', '3.1', '3.2', '3.3'],
        ax = plot.subplot(fig=fig, grid=gs[3:4,i], func='sns.countplot', 
                          data=stats[stats.livestock==ty], 
                          pf_x='scenario', pf_stat='percent',
                          pf_order=['1', '2', '3'],
                          la_xlabel='Scenario', la_ylabel=ylabel,
                          la_title='', lg_title=False)

    if full:
        fn = f'farms_to_cells_dist_full_{state}.pdf'
    else:
        fn = f'farms_to_cells_dist_{state}.pdf'

    plot.savefig(fn)

if __name__ == '__main__':
    # parser
    parser=argparse.ArgumentParser(description=DESC,
            formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-s', '--state', required=True, help="Lower case")
    parser.add_argument('--hspace', type=float, default=-.5, help="Lower case")
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()

    try:
        statefp = STATE_FIPS[args.state]
    except KeyError:
        raise KeyError('State name should be all lower case.')

    # Load data and process it
    counties = loader.load('usa_county_shapes')
    counties = counties.astype({'statefp': 'int', 'countyfp': 'int'})
    counties = counties[counties.statefp==statefp]

    assg = pd.read_csv('../results/farms_to_cells.csv.zip')
    assg = assg[assg.statefp==statefp]

    heads = pd.read_csv('../results/agcensus_heads_filled_gaps.csv.zip')
    heads = heads[(heads.state_fips_code==statefp) & (heads.county_code!=-1)]
    heads = counties[['countyfp', 'geometry']].merge(heads, 
                    left_on='countyfp', right_on='county_code')

    glw = pd.read_csv('../../data/glw/glw_sans_geom_processed.csv.zip')
    ## glw_county = glw[glw.statefp==statefp][
    ##         ['val','livestock','countyfp']].groupby(
    ##         ['livestock', 'countyfp']).sum().reset_index()
    ## glw_county = counties[['countyfp', 'geometry']].merge(glw_county, 
    ##                 on='countyfp')
    glw = glw[glw.statefp==statefp][['x', 'y', 'val', 'livestock']]

    glw_cells = gpd.read_file('../../data/glw/glw_cells.shp.zip')

    stats = pd.read_csv('../results/stats_farms_to_cells.csv.zip')
    stats = stats[stats.state==statefp].copy()

    assg = glw_cells.merge(assg, on=['x', 'y'])
    glw = glw_cells.merge(glw, on=['x', 'y'])

    print(args.state)

    #dist(args.state, glw_county, heads, assg, counties, stats, 
    dist(args.state, glw, heads, assg, counties, stats, 
         hspace=args.hspace, full=args.full)

