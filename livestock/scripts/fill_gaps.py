DESC = '''
Gaps to be filled in AgCensus and inconsistencies rectified.

By: AA

'''

import argparse
import gurobipy as gp
from gurobipy import GRB
from ipfn import ipfn
import numpy as np
import pandas as pd
from pdb import set_trace
from re import sub

from stats import Stats, generate_stats

NSTATES = 50
NCOUNTIES = 3110
INFINITY = 1e8
## nstates = df.state.drop_duplicates().shape[0]
## ncounties = df[df.county!=-1][['state', 'county']].drop_duplicates().shape[0]

COUNTRY_TOTALS = {
        ('hogs', 'dummy'): 73817751,
        ('chukars', 'dummy'): 1048883,
        ('ckn-layers', 'dummy'): 388509039,
        ('ckn-pullets', 'dummy'): 144030599,
        ('ckn-roosters', 'dummy'): 7720779,
        ('ducks', 'dummy'): 4449078,
        ('rheas', 'dummy'): 1144,
        ('emus', 'dummy'): 12580,
        ('ostriches', 'dummy'): 3523,
        ('poultry-other', 'dummy'): 84353,
        ('partridges', 'dummy'): 61169,           # Hungarian partridges
        ('peafowl', 'dummy'): 55053,              # Peacocks and peahens
        ('pheasants', 'dummy'): 3280101,          
        ('pigeons', 'dummy'): 303169,   
        ('quail', 'dummy'): 9294424,
        ('turkeys', 'dummy'): 97312583,
        }

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

def fill_counts(df, tot):
    # We fill the gaps using ILP
    model = gp.Model()
    df = df.reset_index(drop=True)
    
    # Number of variables
    k = df.shape[0]
    
    # Add variables with bounds
    lb = df.lb.values
    ub = df.ub.values

    fixed = 0
    for i,h in enumerate(df.heads.tolist()):
        if h != -1:
            lb[i] = h
            ub[i] = h
            fixed += h
        else:
            if lb[i] > ub[i]:
                set_trace()
                raise ValueError('Bounds violated.')
        
    vars = [model.addVar(
        lb=lb[i], 
        ub=ub[i], name=f"x{i}") for i in range(k)]
    lambda0 = model.addVar(lb=0, name='lambda0')

    # Constraint: sum of variables
    model.addConstr(gp.quicksum(vars) == tot, "sum_of_variables")

    # Constraint: lambda0 bound
    for i in range(k):
        model.addConstr(vars[i] - lb[i]<=lambda0, "bound on lambda0")

    # Set the objective (e.g., minimize the sum of variables as an example)
    model.setObjective(lambda0, GRB.MINIMIZE)
    
    # Optimize the model
    model.optimize()

    if not model.sol_count:
        set_trace()
    
    # Print the values of variables
    vars = [(v.varName,v.X) for v in model.getVars() if not v.varName=='lambda0']
    vdf = pd.DataFrame(vars)
    vdf.loc[:, 0] = vdf[0].str[1:].astype('int')

    df = df.merge(vdf, left_index=True, right_on=0)
    df = df.rename(columns={1: 'new_heads'})
    
    if (df.new_heads==-1).any():
        raise ValueError('Found -1')
    if df.new_heads.isnull().any():
        raise ValueError('Found NaN')
    return df, lambda0.x, tot-fixed
        
def state_total(df, stats_list):
    # Dual purpose
    # 1. fill gaps in both heads and farms
    # 2. check for inconsistencies
    df = df.sort_values('state')

    stats = Stats()
    stats_list.append(stats)

    subtype = df.head(1).subtype.values[0]
    livestock = df.head(1).livestock.values[0]

    stats.subtype = subtype
    stats.livestock = livestock

    print('--------------------------------------------------')
    print(f'{livestock}, {subtype}')

    tdf = df[(df.category=='state_total') & (df.unit=='heads')][
            ['state', 'value']]

    if not (tdf.value==-1).any():
        print(f'No gaps in state total.')
        stats.status = 'no gaps'
        return df
    else:
        print(f'Gaps in state total.')
        stats.status = 'gaps'

    if subtype == 'all':
        print(f'Ignored.')
        stats.status = 'ignored'
        return df

    tot_heads = COUNTRY_TOTALS[(livestock, subtype)]
    stats.tot_heads = tot_heads

    fdf = df[(df.category=='state_by_farmsize') & 
            (df.unit=='operations')][
                    ['state', 'size_min', 'size_max', 'value']]

    if fdf.shape[0]:
        if (fdf.value==-1).sum():
            raise ValueError('Missing farm counts.')

        fdf['lb'] = fdf.size_min * fdf.value
        fdf['ub'] = fdf.size_max * fdf.value

        bounds = fdf.groupby('state')[['lb', 'ub']].sum().reset_index()
        stats.farms_by_size = True
    else:
        # lower bound is the number of farms in that state
        bounds = df[(df.category=='state_total') & (df.unit=='operations')][
                ['state', 'value']].rename(columns={'value': 'lb'})
        # upper bound is the deficit in country total
        bounds['lb'] = 0
        bounds['ub'] = tot_heads - tdf.value.sum()
        stats.farms_by_size = False

    tdf = tdf.merge(bounds, on='state', how='left')

    # Sometimes, heads are provided at state level by farmzise. 
    # We use that to redefine lb
    sbf_heads = df[(df.unit=='heads') & 
                   (df.category=='state_by_farmsize')].copy()
    stats.heads_state_by_farmsize = False
    if sbf_heads.shape[0]:
        stats.heads_by_farmsize = True
        sbf_heads.loc[sbf_heads.value==-1, 'value'] = 0
        sbf_farms = df[(df.unit=='operations') & 
                       (df.category=='state_by_farmsize')].copy()
        sbf_farms = sbf_farms.rename(columns={'value': 'ops'})
        sbf_heads = sbf_heads.merge(
                sbf_farms[['state', 'size_min', 'ops']],
                on=['state', 'size_min'])
        sbf_heads.value = np.maximum(sbf_heads.ops*sbf_heads.size_min,
                sbf_heads.value)
        
    # Sometimes, heads are provided at the county level.
    # Partial counts are provided in two ways -- county totals and 
    # county-by-farmsize. Each can be used to get lower bounds for the
    # state total. We use them to redefine lb.
    ### County-by-farmsize and comparing with state-by-farmsize
    cbf_heads = df[(df.unit=='heads') & 
                   (df.category=='county_by_farmsize')].copy()
    stats.heads_county_by_farmsize = False
    if cbf_heads.shape[0]:
        stats.county_by_farmsize = True
        cbf_heads.loc[cbf_heads.value==-1, 'value'] = 0
        cbf_farms = df[(df.unit=='operations') & 
                       (df.category=='county_by_farmsize')].copy()
        cbf_farms = cbf_farms.rename(columns={'value': 'ops'})
        cbf_heads = cbf_heads.merge(
                cbf_farms[['state', 'county', 'size_min', 'ops']],
                on=['state', 'county', 'size_min'])
        cbf_heads.value = np.maximum(cbf_heads.ops*cbf_heads.size_min,
                cbf_heads.value)
        cbf_state = cbf_heads.groupby(['state', 'size_min']
                )['value'].sum().reset_index()
        cbf_state = cbf_state.merge(sbf_heads[['state', 'size_min', 'value']],
                on=['state', 'size_min'], suffixes=('', '_y'))
        cbf_state.value = np.maximum(cbf_state.value, cbf_state.value_y)

        cbf_lb = cbf_state.groupby('state')['value'].sum().reset_index()

        tdf = tdf.merge(cbf_lb, on='state', how='left', suffixes=('', '_cbf'))
        tdf.lb = np.maximum(tdf.lb, tdf.value_cbf)

    ### County totals and comparing with county-by-farmsize
    ct_heads = df[(df.unit=='heads') & 
                   (df.category=='county_total')].copy()
    stats.heads_county_totals = False
    if ct_heads.shape[0]:
        stats.heads_county_totals = True
        ct_heads.loc[ct_heads.value==-1, 'value'] = 0
        if cbf_heads.shape[0]:
            cbf_county = cbf_heads.groupby(['state', 'county']
                    ).sum().reset_index()
            cbf_county = cbf_county.merge(ct_heads[
                ['state', 'county', 'value']],
                on=['state', 'county'], suffixes=('', '_y'))
            cbf_county.value = np.maximum(cbf_county.value, 
                    cbf_county.value_y)
            ct_lb = cbf_county.groupby('state')['value'].sum().reset_index()
        else:
            ct_lb = ct_heads.groupby('state')['value'].sum().reset_index()

        tdf = tdf.merge(ct_lb, on='state', how='left', suffixes=('', '_ct'))
        tdf.lb = np.maximum(tdf.lb, tdf.value_ct)
    tdf = tdf.rename(columns={'value': 'heads'})

    tdf, stats.lambda0, stats.deficit = fill_counts(tdf, tot_heads)
    df.loc[((df.category=='state_total') 
            & (df.unit=='heads')), 'value'] = tdf.new_heads.values
    stats.diff = tdf.new_heads.sum() - tdf.heads.sum()
    return df

def state_by_farmsize(df, stats_list):
    # Dual purpose
    # 1. fill gaps in both heads and farms
    # 2. check for inconsistencies

    df = df.sort_values(['size_min', 'size_max'])

    stats = Stats()
    stats_list.append(stats)

    subtype = df.head(1).subtype.values[0]
    state = df.head(1).state.values[0]
    livestock = df.head(1).livestock.values[0]

    stats.subtype = subtype
    stats.state = state
    stats.livestock = livestock

    print('--------------------------------------------------')
    print(f'{state}, {livestock}, {subtype}.')
    
    # Go ahead only if this is a subtype
    if subtype == 'all':
        print(f'ignored.')
        stats.status = 'ignored'
        return df

    tdf = df[df.category=='state_by_farmsize'][
            ['unit', 'size_min', 'size_max', 'value']].pivot(
                    index=['size_min', 'size_max'], columns='unit',
                    values='value').reset_index()
    stats.state_by_farmsize = True
    if not tdf.shape[0]:
        stats.state_by_farmsize = False
        print(f'No population by farmsize provided.')
        return df

    tot_heads = df[(df.unit=='heads') & 
                   (df.category=='state_total')].value.values[0]
    tot_farms = df[(df.unit=='operations') & 
                   (df.category=='state_total')].value.values[0]
    tdf['lb'] = tdf.size_min * tdf.operations
    tdf['ub'] = tdf.size_max * tdf.operations
    if subtype=='chukars':
        set_trace()

    # Are there missing farms?
    if tdf.operations.sum() != tot_farms:
        print('Sum of farms not equal to total farms.')
        set_trace()

    # Missing farms
    if (tdf.operations==-1).any():
        print('Missing farms')
        set_trace()

    # Is sum of heads > total?
    if tdf.heads.sum() > tot_heads:
        print('Sum of heads > total heads.')
        set_trace()

    # Basic checks done.
    # Missing heads
    if not tdf[tdf.heads==-1].shape[0]:
        print(f'No gaps in state by farmsize.')
        stats.status = 'no gaps'
        return df
    else:
        print(f'Gaps in state by farmsize.')
        stats.status = 'gaps'

    # Refine lower bound if county counts by farmsize is present
    stats.county_by_farmsize = False
    cbf_heads = df[(df.unit=='heads') & 
                   (df.category=='county_by_farmsize')].copy()
    if cbf_heads.shape[0]:
        stats.county_by_farmsize = True
        cbf_heads.loc[cbf_heads.value==-1, 'value'] = 0
        cbf_lb = cbf_heads.groupby('size_min')['value'].sum().values
        tdf.lb = np.maximum(tdf.lb, cbf_lb)
    
    stats.tot_heads = tot_heads
    tdf, stats.lambda0, stats.deficit = fill_counts(tdf, tot_heads)
    df.loc[((df.category=='state_by_farmsize') 
            & (df.unit=='heads')), 'value'] = tdf.new_heads.values
    stats.diff = tdf.new_heads.sum() - tdf.heads.sum()
    return df

def county_total(df, stats_list):
    # Dual purpose
    # 1. fill gaps in both heads and farms
    # 2. check for inconsistencies

    df = df.sort_values('county')

    stats = Stats()
    stats_list.append(stats)

    subtype = df.head(1).subtype.values[0]
    state = df.head(1).state.values[0]
    livestock = df.head(1).livestock.values[0]

    print('--------------------------------------------------')
    print(f'{state}, {livestock}, {subtype}.')

    # Go ahead only if this is a subtype
    if subtype == 'all':
        print(f'Ignored.')
        stats.status = 'ignored'
        return df


    tdf = df[(df.category=='county_total') & (df.unit=='heads')][
            ['county', 'value']]
    try:
        tot_heads = df[(df.category=='state_total') & (df.unit=='heads')
                ].value.values[0]
    except:
        set_trace()
    tot_farms = df[(df.category=='state_total') & (df.unit=='operations')
            ].value.values[0]
    stats.tot_heads = tot_heads
    stats.tot_farms = tot_farms

    # Is sum of heads > state total?
    if tdf.value.sum() > tot_heads:
        print('Sum of heads > total heads.')
        set_trace()

    # Basic checks done.
    # Missing heads
    if not (tdf.value==-1).sum():
        print(f'No gaps in county totals.')
        stats.status = 'no gaps'
        return df
    else:
        print(f'Gaps in county totals.')
        stats.status = 'gaps'

    fdf = df[(df.category=='county_by_farmsize') & 
            (df.unit=='operations')][
                    ['county', 'size_min', 'size_max', 'value']]

    if (fdf.value==-1).sum():
        print('Missing farm counts.')
        set_trace()

    if fdf.shape[0]:
        stats.farms_by_size = True
        fdf['lb'] = fdf.size_min * fdf.value
        fdf['ub'] = fdf.size_max * fdf.value
        bounds = fdf.groupby('county')[['lb', 'ub']].sum().reset_index()
        tdf = tdf.merge(bounds, on='county', how='left')
    else:
        stats.farms_by_size = False
        tdf['lb'] = 0
        tdf['ub'] = tot_heads

    # Refine lower bounds if county-level counts by farmsize is present
    stats.county_by_farmsize = False
    cbf_heads = df[(df.unit=='heads') & 
                   (df.category=='county_by_farmsize')].copy()
    if cbf_heads.shape[0]:
        stats.county_by_farmsize = True
        cbf_heads.loc[cbf_heads.value==-1, 'value'] = 0
        cbf_lb = cbf_heads.groupby('county')['value'].sum().reset_index()
        tdf = tdf.merge(cbf_lb, on='county', suffixes=('', '_y'))
        tdf.lb = np.maximum(tdf.lb, tdf.value_y)

    tdf = tdf.rename(columns={'value': 'heads'})

    tdf, stats.lambda0, stats.deficit = fill_counts(tdf, tot_heads)
    df.loc[((df.category=='county_total') 
            & (df.unit=='heads')), 'value'] = tdf.new_heads.values
    stats.diff = tdf.new_heads.sum() - tdf.heads.sum()
    return df

def county_by_farmsize(df, stats_list):
    state = df.name[0]
    livestock = df.name[1]
    subtype = df.name[2]

    stats = Stats()
    stats_list.append(stats)

    stats.subtype = subtype
    stats.state = state
    stats.livestock = livestock

    print('--------------------------------------------------')
    print(f'{state}, {livestock}, {subtype}')

    county_by_farmsize_ind = (df.category=='county_by_farmsize')

    stats.county_by_farmsize = True
    if not county_by_farmsize_ind.any():
        stats.county_by_farmsize = False
        print('No data on county counts by farmsize. Creating a dummy row.')
        name = df.name
        tdf = df[df.category=='county_total'].copy()
        tdf.loc[:, 'category'] = 'county_by_farmsize'
        tdf.size_min = 0
        df = pd.concat([df, tdf], ignore_index=True)
        df.name = name
        return df

    county_by_farmsize_heads_ind = (df.unit=='heads') & \
            (df.category=='county_by_farmsize')
    stats.county_by_farmsize_heads = True
    if not county_by_farmsize_heads_ind.any():
        stats.county_by_farmsize_heads = False
        print('No data on county head counts by farmsize. Creating a dummy row.')
        name = df.name
        tdf = df[(df.unit=='heads') & (df.category=='county_total')].copy()
        tdf.loc[:, 'category'] = 'county_by_farmsize'
        tdf.size_min = 0
        df = pd.concat([df, tdf], ignore_index=True)
        df.name = name
        return df

    if subtype=='all':
        print('Ignored')
        stats.status = 'ignored'
        return df

    heads = df[df.unit=='heads'].copy()
    farms = df[df.unit=='operations'].copy()

    # Compute seeds
    redacted = (heads.category=='county_by_farmsize') & (heads.value==-1)
    fixed = (heads.category=='county_by_farmsize') & (heads.value!=-1)

    # Checks
    num_redacted = redacted.sum()

    if num_redacted:
        print(f'{state},{livestock},{subtype}: #redacted: {num_redacted}')
    else:
        print(f'{state},{livestock},{subtype}: No gaps. Skipping IPF ...')
        stats.status = 'no gaps'
        return df

    if (heads[heads.category=='state_by_farmsize'].value==-1).sum():
        raise ValueError(f'{state},{livestock}: Total head count missing for some farm sizes for the state')
    if heads[(heads.category=='county_totals') & (heads.value==-1)].shape[0]:
        raise ValueError(f'{state},{livestock}: missing county totals for the state')

    size_min_state = heads[heads.category=='state_by_farmsize'
            ].size_min.drop_duplicates().tolist()
    size_min_county = heads[heads.category=='county_by_farmsize'
            ].size_min.drop_duplicates().tolist()

    if size_min_state != size_min_county:
        raise ValueError('Size mismatch between state and county farm categories.')

    # Keep track of known values that need to be fixed.
    # Create matrix of fixed values
    fdf = heads[heads.category=='county_by_farmsize']

    mat_fdf = fdf.pivot(index='county_code', columns='size_min', 
            values='value').fillna(0)

    # Note that those values that should be zero will be unaffected.
    mat_fdf.replace(-1, 0, inplace=True)

    row_county_fixed_totals = mat_fdf.sum(axis=1).to_numpy()
    col_state_fixed_totals = mat_fdf.sum().to_numpy()

    row_county_totals = heads[heads.category=='county_total'].value.to_numpy()
    col_state_totals = heads[heads.category=='state_by_farmsize'].value.to_numpy()

    adjusted_row_county_totals = row_county_totals - row_county_fixed_totals
    adjusted_col_state_totals = col_state_totals - col_state_fixed_totals

    if (adjusted_row_county_totals<0).sum() or (adjusted_col_state_totals<0).sum():
        raise ValueError('Some elements in the adjusted totals are negative.')

    # Now fill unknown values with seeds
    ## Seed = Middle of frequency bin * #farms
    farms.loc[farms.size_max==-1, 'size_max'] = farms[
            farms.size_max==-1].size_min * 2
    farms['weight'] = (farms.size_min + farms.size_max)/2 * farms.value


    tdf = heads[redacted].merge(farms[['county_code', 'size_min', 'weight']],
                               on=['county_code', 'size_min'])
    heads.loc[redacted, 'value'] = tdf.weight.values
    
    mat_df = heads[heads.category=='county_by_farmsize'].pivot(
            index='county_code', columns='size_min', 
            values='value').fillna(0)
    farms = farms.drop('weight', axis=1)

    # Subtract fixed values from the matrix
    mat_df = mat_df - mat_fdf

    county_list_from_farmsize = mat_df.index.tolist()
    county_list_from_totals = heads[heads.category=='county_total'
            ].county_code.tolist()
    if county_list_from_farmsize != county_list_from_totals:
        raise ValueErro('County lists extracted from farmsize and totals do not match')

    mat = mat_df.values
    mat_ = mat.copy()   # This is just for debugging

    ## county_cats = mat_df.columns.to_numpy()
    ## state_cats = heads[heads.category=='state_by_farmsize'
    ##                    ].size_min.drop_duplicates().to_numpy()

    ipf = ipfn.ipfn(mat, 
            [adjusted_row_county_totals, adjusted_col_state_totals], [[0],[1]],
                    convergence_rate=1e-8, verbose=2)

    mat, conflag, con = ipf.iteration()

    # Put back fixed values
    mat_df = mat_df + mat_fdf

    new_heads = pd.melt(mat_df.reset_index(), id_vars=['county_code'], 
                        var_name='size_min', value_name='value')

    # Clip
    farms['lb'] = farms.size_min * farms.value
    farms['ub'] = farms.size_max * farms.value
    new_heads = new_heads.merge(farms[farms.category=='county_by_farmsize'][
        ['county_code', 'size_min', 'lb', 'ub']],
        on=['county_code', 'size_min'], how='left')
    new_heads.value = new_heads[['value', 'ub']].min(axis=1)
    new_heads.value = new_heads[['value', 'lb']].max(axis=1)
    new_heads = new_heads.drop(['lb', 'ub'], axis=1)
    farms = farms.drop(['lb', 'ub'], axis=1)

    if new_heads.value.min() < 0:
        raise ValueError('Negative!')

    new_heads[new_heads.value<0] = 0
    new_heads = new_heads.sort_values(['county_code', 'size_min'])
    new_heads['category'] = 'county_by_farmsize'

    county_totals = new_heads[['county_code', 'value']
            ].groupby('county_code').sum().reset_index()
    county_totals['category'] = 'county_total'
    county_totals['size_min'] = -1

    new_heads = pd.concat([new_heads, county_totals])
    heads = heads.merge(new_heads, how='left', 
            on=['county_code', 'size_min', 'category'])
    heads = heads.drop('value_x', axis=1)
    heads = heads.rename(columns={'value_y': 'value'})
    heads.loc[heads.value.isnull(), 'value'] = heads.loc[
            heads.value.isnull()].value_original
    heads.value = heads.value.astype('int')

    # Verify if any fixed value has changed
    heads['test'] = (heads.value!=heads.value_original)
    if heads[(heads.value_original!=-1) &
            (heads.category=='county_by_farmsize')].test.sum():
        raise ValueError('Some fixed values have changed')
    heads = heads.drop('test', axis=1)

    odf = pd.concat([df[df.category!='county_by_farmsize'], 
        heads[heads.category=='county_by_farmsize'],
        farms])

    odf.name = df.name
    if (odf[odf.category.isin(
        ['county_total', 'state_by_farmsize', 
            'county_by_farmsize'])].value==-1).any():
        raise ValueError('Unassigned county_by_farmsize')
    ## if state==1 and livestock=='cattle':
    ##     set_trace()

    stats.status = 'ipf'
    stats.iterations = con.shape[0]

    return odf

def make_feasible(df, stats_list):

    stats = Stats()
    stats_list.append(stats)

    stats.state = df.name[0]
    stats.county = df.name[1]
    stats.livestock = df.name[2]

    print(stats.state, stats.county, stats.livestock)

    if not stats.livestock in ['cattle', 'hogs', 'sheep']:
        return df

    heads = df[df.unit=='heads']
    farms = df[df.unit=='operations']

    # farms
    farms = farms.sort_values(by='size_min')
    fdf = farms[farms.category=='county_by_farmsize'][
            ['size_min', 'size_max', 'subtype', 'value']].pivot(
                    index=['size_min', 'size_max'], columns='subtype',
                    values='value').reset_index().fillna(0)
    fdf = fdf.astype('int')

    # heads
    heads = heads.sort_values(by='size_min')
    hdf = heads[heads.category=='county_by_farmsize'][
            ['size_min', 'size_max', 'subtype', 'value']].pivot(
                    index=['size_min', 'size_max'], columns='subtype',
                    values='value').reset_index().fillna(0)
    hdf = hdf.astype('int')

    model = gp.Model('MakeFeasible')

    # subtypes
    subtypes = fdf.columns.tolist()
    for ele in ['size_min', 'size_max', 'all']:
        subtypes.remove(ele)

    ell = fdf.shape[0]
    Wmin = fdf.size_min.values
    Wmax = fdf.size_max.values

    ### extract farms/heads of livestock
    Fi = fdf['all'].values
    Hi = hdf['all'].values
    Fgk = {} # Number of farms of subtype category
    Hgk = {} # Number of heads of subtype category
    for subtype in subtypes:
        Fgk[subtype] = fdf[subtype].values
        Hgk[subtype] = hdf[subtype].values

    stats.farms = sum(Fi)
    tot_heads = hdf[subtypes].sum().sum()
    stats.heads = tot_heads
    stats.heads_all = sum(Hi)
    stats.categories = ell
    stats.subtypes = len(subtypes)

    # Variables
    h = model.addVars(subtypes, ell, lb=0, vtype=GRB.INTEGER, name='h')
    alpha = model.addVar(name="alpha", vtype=GRB.INTEGER)

    # Constraints
    # Category farm size constraint
    for g in subtypes:
        for k in range(ell):
            model.addConstr(h[g,k] >= Wmin[k]*Fgk[g][k], 
                    f"Lower bound on farm size")
            model.addConstr(h[g,k] <= Wmax[k]*Fgk[g][k], 
                    f"Upper bound on farm size")
    
    # Total population constraint
    tot_pop_lb = sum([Wmin[i]*Fi[i] for i in range(ell)])
    tot_pop_ub = sum([Wmax[i]*Fi[i] for i in range(ell)])
    model.addConstr(gp.quicksum(h[g,k] for g in subtypes for k in range(ell))
            >= tot_pop_lb)
    model.addConstr(gp.quicksum(h[g,k] for g in subtypes for k in range(ell))
            <= tot_pop_ub)

    # Minimization criterion
    for g in subtypes:
        for k in range(ell):
            try:
                model.addConstr(h[g,k] - Hgk[g][k] <= alpha)
                model.addConstr(h[g,k] - Hgk[g][k] >= -alpha)
            except:
                set_trace()

    # Set objective
    model.setObjective(alpha, GRB.MINIMIZE)

    model.optimize()

    hgk = {}
    for g in subtypes:
        hgk[g] = []
        for k in range(ell):
            hgk[g].append(h[g,k].X)
    hdf_ = pd.DataFrame(hgk)

    stats.alpha = alpha.X

    if alpha.X == 0 and abs(hdf_[subtypes] - hdf[subtypes]).sum().sum():
        raise ValueError('Mismatch of heads.')

    if not alpha.X:
        return df
    else:
        hdf_['size_min'] = hdf.size_min
        tdf = hdf_.set_index('size_min').stack().reset_index()
        tdf = tdf.rename(columns={'level_1': 'subtype', 0: 'new_value'})
        name = df.name
        df = df.merge(tdf, on=['size_min', 'subtype'])
        df.loc[df.unit=='heads', 'value'] = df[df.unit=='heads'].new_value.values
        df.drop('new_value', axis=1)
        df.name = name
        return df

if __name__ == '__main__':
    # parser
    parser=argparse.ArgumentParser(description=DESC, 
    formatter_class=argparse.RawTextHelpFormatter)
    args = parser.parse_args()

    # Load datasets
    df = pd.read_csv('../../data/agcensus/agcensus_heads_farms.csv.zip')
    df.loc[df.size_max==-1, 'size_max'] = INFINITY

    # Sanity checks (simple/global)
    sanity_checks(df)

    # Copy original values
    df['value_original'] = df.value

    # State totals: fill gaps
    state_stats = []
    stdf = df[df.category.isin(
        ['state_total', 'state_by_farmsize', 'county_by_farmsize',
            'county_total'])].groupby(['livestock', 'subtype']
                    ).apply(state_total, state_stats)
    stdf = stdf.reset_index(drop=True)
    stdf = stdf[stdf.category=='state_total']

    if ((stdf.value==-1) & (stdf.subtype!='all')).any():
        raise ValueError('Still unfilled state totals.')
    if stdf.value.isnull().any():
        raise ValueError('Found some nulls')
    ttdf = stdf[stdf.value_original!=-1]
    if (ttdf.value_original!=ttdf.value).any():
        raise ValueError('State totals: some non -1 values changed.')
    generate_stats(state_stats, out='stats_gaps_totals_state.csv')

    ### Update state total before proceeding to the next step
    df = df.drop(df[df.category=='state_total'].index)
    df = pd.concat([df, stdf])

    # State by farmsize: fill gaps
    state_farmsize_stats = []
    sdf = df[df.category.isin(['state_by_farmsize', 'county_by_farmsize',
            'state_total'])].groupby(
            ['state', 'subtype', 'livestock']).apply(state_by_farmsize,
                    state_farmsize_stats)
    sdf = sdf.reset_index(drop=True)
    generate_stats(state_farmsize_stats, 
            out='stats_gaps_totals_state_farmsize.csv')

    ttdf = sdf[sdf.category=='state_by_farmsize']
    if ((ttdf.value==-1) & (ttdf.subtype!='all')).any():
        raise ValueError('Still unfilled state totals.')
    if ttdf.value.isnull().any():
        raise ValueError('Found some nulls')

    # County totals: fill gaps
    county_farmsize_stats = []
    cdf = df[df.category.isin(
        ['county_total', 'state_total', 'county_by_farmsize'])].groupby(
            ['state', 'livestock', 'subtype']).apply(county_total,
                    county_farmsize_stats)
    cdf = cdf.reset_index(drop=True)
    generate_stats(county_farmsize_stats, 
            out='stats_gaps_totals_county_totals.csv')
    ttdf = cdf[cdf.category=='county_total']
    if ((ttdf.value==-1) & (ttdf.subtype!='all')).any():
        raise ValueError('Still unfilled county totals.')
    if ttdf.value.isnull().any():
        raise ValueError('Found some nulls')
    df = pd.concat([sdf, cdf], ignore_index=True).drop_duplicates()

    tdf = df[(df.category.isin(['state_by_farmsize', 'county_total'])) &
            (df.subtype!='all')]
    if (tdf.value==-1).any():
        raise ValueError('Some gaps still not filled.')

    # County by farm size: fill gaps
    df = df.sort_values(
            by=['size_min', 'size_max', 'state_code', 'county_code'])

    stats_list = []

    ### Process by state, livestock, subtype
    df = df.groupby(['state_code', 'livestock', 'subtype'],
            ).apply(county_by_farmsize, stats_list, 
                    include_groups=False).reset_index().drop('level_3', axis=1)
    generate_stats(stats_list, out='stats_gaps_county_by_farmsize.csv')

    # Make feasible
    stats_list = []
    df.to_csv('temp.csv.zip', index=False)

    ## ### Process by state, livestock, subtype
    ## cdf = df[df.category=='county_by_farmsize'].groupby(
    ##         ['state_code', 'county_code', 'livestock'],
    ##         ).apply(make_feasible, stats_list,
    ##                 include_groups=False).reset_index().drop('level_3', axis=1)
    ## generate_stats(stats_list, out='stats_make_feasible.csv')

    ## df = pd.concat([df[df.category!='county_by_farmsize'], cdf])

    df_ = df.copy() # just for debugging

    df = df.astype({'value': 'int', 'value_original': 'int'})

    df.to_csv('agcensus_filled_gaps.csv.zip', index=False)

    print('Input should match output in size.')
    print('Input', df.shape)
    print('Output', df.shape)
    print('Gaps filled:', (df.value!=df.value_original).sum())
    print('Nulls', df.value.isnull().sum())

    print('The commented code below was used to check the totals after farm sizes were added to ckn-layers')
    ## oodf = pd.read_csv('../results/agcensus_processed1_filled_totals.csv.zip')
    ## xx = df.columns.tolist()
    ## xx.remove('value_original')
    ## xx.remove('value')
    ## df = df.merge(odf, on=xx)
    ## df.test = abs(df.test)
    ## df[df.subtype!='ckn-layers'].test.max()

