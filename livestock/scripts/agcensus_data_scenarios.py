DESC = '''
Analysis of data scenatios.

By: AA

'''

import argparse
import numpy as np
import pandas as pd
from pdb import set_trace
from re import sub

from aaviz import plot

NSTATES = 50
NCOUNTIES = 3110
## nstates = df.state.drop_duplicates().shape[0]
## ncounties = df[df.county!=-1][['state', 'county']].drop_duplicates().shape[0]

def sanity_checks(df):

    if df.isnull().sum().sum():
        raise ValueError('Some rows are null.')

    # Aggregation check
    if (df.value<-1).sum():
        print('WARNING: Some values are -2 or lower. Issue with aggregation.')

    # Check for repeated rows with different values
    cols = df.columns.tolist()
    cols.remove('value')
    rr = df.groupby(cols).nunique().reset_index()
    rr = rr[rr.value!=1]
    if rr.value.sum():
        print('WARNING: Some rows are repeated with differing values.')

def farm_size_checks(df):
    # Check for duplicate entries and see if the corresponding values differ.
    # This could be due to issues of aggregation.
    set_trace()

def plot_scenarios(df):
    fig, gs = plot.initiate_figure(x=10, y=4, 
                                   gs_nrows=1, gs_ncols=1,
                                   color='tableau10',
                                   scilimits=[-2,2])

    df.category = df.category.str.replace('_', ' ')
    tp = df.groupby(['subtype', 'category']).agg({
        'val': ['sum', 'count']}).reset_index()
    tp.columns = ['subtype', 'category', 'instances', 'count']
    tp.loc[tp.category=='state by farmsize', 'perc'] = tp[
            tp.category=='state by farmsize']['count']/NSTATES*100
    tp.loc[tp.category.isin(['county total', 'county by farmsize']), 'perc'] = tp[
            tp.category.isin(
                ['county total', 'county by farmsize'])]['count']/NCOUNTIES*100

    ax = plot.subplot(fig=fig, grid=gs[0,0], func='sns.barplot', 
                      data=tp,
                      pf_x='category',
                      pf_y='perc',
                      pf_order=['state by farmsize', 'county total', 'county by farmsize'],
                      pf_hue='subtype',
                      pf_hue_order=['all', 'milk', 'beef', 'other'],
                      la_title='Cattle',
                      la_ylabel='\\% instances',
                      la_xlabel='Livestock subtype'
                      )

    tp.category = pd.Categorical(
            tp.category, 
            categories=['state by farmsize', 'county total', 'county by farmsize'],
            ordered=True)
    tp.subtype = pd.Categorical(
            tp.subtype, 
            categories=['all', 'milk', 'beef', 'other'],
            ordered=True)
    tp = tp.sort_values(by=['category', 'subtype'])
    plot.text(ax=ax, data=tp, x='x', y='perc', textcol='count') 
    plot.savefig('missing_data_scenarios.pdf')

if __name__ == '__main__':
    # parser
    parser=argparse.ArgumentParser(description=DESC, 
    formatter_class=argparse.RawTextHelpFormatter)
    args = parser.parse_args()

    # Load datasets
    df = pd.read_csv('../../data/agcensus/agcensus_heads_farms.csv.zip')
    sanity_checks(df)

    instance_list = []
    for cat in df.category.drop_duplicates().tolist():
        tdf = df[(df.category==cat) & (df.value==-1)][
            ['state', 'county', 'subtype', 'value']].groupby(
                    ['state', 'county', 'subtype']).size().reset_index()
        if not tdf.shape[0]:
            continue
        tdf['category'] = cat
        instance_list.append(tdf)

    instances = pd.concat(instance_list)
    instances = instances.rename(columns={0: 'val'})
    instances.to_csv('missing_data_scenarios.csv', index=False)

    plot_scenarios(instances)


