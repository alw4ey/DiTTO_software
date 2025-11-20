DESC = '''
Collect all assignements and stats.

By: AA

'''

from glob import glob
import pandas as pd
from pdb import set_trace

dfl = []
failed = []
for ff in glob('farms_to_cells_[0-9]*zip'):
    try:
        dfl.append(pd.read_csv(ff))
    except:
        failed.append(ff)

print(f'Number of successful instances: {len(dfl)}')
print(f'Number of instances failed to load: {len(failed)}')
print('farms_to_cells.csv.zip ...')

df = pd.concat(dfl)

## df = pd.read_csv('../work/farms_to_cells.csv.zip')
# Unique index for each farm
df = df.sort_values(['state_code', 'county_code'])
farms = df[['fid', 'state_code', 'county_code', 'livestock']
        ].drop_duplicates().reset_index(drop=True).reset_index()
farms = farms.rename(columns={'index': 'new_fid'})
df = df.merge(farms, on=['fid', 'state_code', 'county_code', 'livestock'], 
        how='left').drop(
        'fid', axis=1).rename(columns={'new_fid': 'fid'})

poultry = df.livestock.drop_duplicates().tolist()
for ll in ['hogs', 'cattle', 'sheep']:
    try:
        poultry.remove(ll)
    except:
        pass

ind = df.livestock.isin(poultry)
df.loc[ind, 'subtype'] = df[ind].livestock
df.loc[ind, 'livestock'] = 'poultry'
tdf = df[df.livestock=='poultry'].copy()
tdf.subtype = 'all'
df = pd.concat([df, tdf])
df[['fid', 'state_code', 'county_code', 'livestock', 'subtype', 'x', 'y', 'heads']
        ].to_csv('farms_to_cells.csv.zip', index=False)

dfl = []
for ff in glob('stats_farms_to_cells_[0-9]*csv'):
    try:
        tdf = pd.read_csv(ff)
        ## if tdf.shape[0] > 1:
        ##     tdf = tdf[~tdf.county.isnull()]
        ## if tdf.county=='False':
        ##     set_trace()
        dfl.append(tdf)
    except:
        failed.append(ff)
print(f'Number of successful stats: {len(dfl)}')
print(f'Number of stats failed to load: {len(failed)}')

df = pd.concat(dfl)

print(f'Failed to execute: {df.gf_sol.isnull().sum()}')
print(f'GF: failed instances: {(df.gf_sol=="failed").sum()}')
print(f'GF: sub-optimal instances: {(df.gf_sol=="non-optimal").sum()}')
print(f'GF: infeasible instances: {(df.lambda4!=0).sum()}')
print(f'FC: failed instances: {(df.fc_sol=="failed").sum()}')
print(f'FC: sub-optimal instances: {(df.fc_sol=="non-optimal").sum()}')

ind = df.livestock.isin(poultry)
df.loc[ind, 'subtype'] = df[ind].livestock
df.loc[ind, 'livestock'] = 'poultry'
df.to_csv('stats_farms_to_cells.csv.zip', index=False)

print('failed_stats.csv ...')
with open('failed_stats.csv', 'w') as f:
    for ff in failed:
        f.write(ff+'\n')
