DESC = '''
Verification of head/farm counts.

By: AA
'''

import argparse
from aadata import loader
from aaviz import plot
import numpy as np
import pandas as pd
from pdb import set_trace

if __name__ == '__main__':
    # Load data and process it
    assg = pd.read_csv('../results/farms_to_cells.csv.zip')
    heads = pd.read_csv('../../data/agcensus/agcensus_heads.csv.zip')
    heads = heads[heads.commodity_desc!='goats']
    stats = pd.read_csv('../results/stats_farms_to_cells.csv.zip')

    # State counts
    assg_state = assg[['statefp', 'livestock', 'heads']].groupby([
        'statefp', 'livestock']).sum()
    heads_state = heads[heads.category=='state_by_farmsize'][
            ['state_fips_code', 'commodity_desc', 'value']].groupby(
            ['state_fips_code', 'commodity_desc']).sum()
    heads_state = heads_state.rename_axis(
            index={'state_fips_code': 'statefp', 'commodity_desc': 'livestock'})
    heads_state = heads_state.rename(columns={'value': 'agcensus'})
    
    stats_state = stats[['state', 'livestock', 'scenario']
                        ].groupby(['state', 'livestock']).value_counts(
                                      normalize=True).reset_index()
    stats_state = stats_state.pivot(index=['state', 'livestock'], 
                                    columns='scenario').fillna(0)['proportion']
    stats_state = stats_state.rename_axis(
            index={'state': 'statefp', 'livestock': 'livestock'})

    # Combine them
    heads_state = heads_state.join(assg_state)
    heads_state = heads_state.join(stats_state)

    heads_state['error'] = 100 * (heads_state.agcensus-heads_state.heads
                            ).abs()/heads_state.agcensus

    heads_state = heads_state.sort_values(by='error', ascending=False)

    print(heads_state.head(20))
    set_trace()

