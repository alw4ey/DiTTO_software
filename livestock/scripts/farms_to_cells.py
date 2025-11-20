DESC = '''
Find assignment of farms (from AgCensus) to cells (GLW) for each county.
This is done by using an ILP which comes up with an assignment that tries
to reduce the gap of head counts of AgCensus and GLW for each cell.

By: SSR, ChatGPT, and AA

To run this on interactive, set up the following environment:
    interactive.sh <xx>
    module load gurobi
    export PYTHONPATH=$EBROOTGUROBI/lib/python3.11_utf32

'''

import argparse
import gurobipy as gp
from gurobipy import GRB
import numpy as np
from os import environ
import pandas as pd
from pdb import set_trace
from scipy.stats import pearsonr
import sys
from time import time

from aadata import loader
from aautils import geometry
from stats import Stats, generate_stats

TIME_LIMIT = 3600
INFINITY = int(1e12)
GF_OPT_TOL_PERC = 1 
#GF_OPT_TOL_MAX = 5
FC_OPT_TOL_PERC = .1 
FC_OPT_TOL_MAX = 5

GLW_MAP = {'cattle': 'cattle', 
    'sheep': 'sheep', 
    'hogs': 'hogs',
    'chukars': 'poultry',
    'ckn-broilers': 'poultry', 
    'ckn-layers': 'poultry', 
    'ckn-pullets': 'poultry', 
    'ckn-roosters': 'poultry', 
    'ducks': 'poultry', 
    'emus': 'poultry', 
    'geese': 'poultry', 
    'guineas': 'poultry', 
    'ostriches': 'poultry', 
    'poultry-other': 'poultry', 
    'peafowl': 'poultry', 
    'pheasants': 'poultry', 
    'pigeons': 'poultry', 
    'quail': 'poultry', 
    'rheas': 'poultry', 
    'turkeys': 'poultry', 
    'partridges': 'poultry'
    }


def assign_category(heads, Wmin, Wmax):
    if heads == 0:
        return -1
    cat = (heads<=Wmax) & (heads>=Wmin)
    if cat.sum() > 1:
        raise ValueError('More than two categories identified.')
    return np.where(cat)[0][0]

def generate_farms(hdf, fdf, stats, livestock):

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

    # Model
    model = gp.Model('FarmAssignment')

    # Variables
    h = {}  # Population of subtype gamma in farm f of category i
    x = {}  # Indicator variable for subtype category assignment
    z = {}  # Population of farm in subtype category k

    # Create variables for h[i,f,gamma] for each farm, category, and subtype
    ifg = []
    ifgk = []
    for i in range(ell):
        for f in range(Fi[i]):
            for g in subtypes:
                ifg.append((i,f,g))
                for k in range(ell):
                    ifgk.append((i,f,g,k))
    h = model.addVars(ifg, lb=0, vtype=GRB.INTEGER, name='h') 
    x = model.addVars(ifgk, lb=0, vtype=GRB.BINARY, name='x')
    y = model.addVars(ifgk, vtype=GRB.CONTINUOUS, name='y')
    z = model.addVars(ifgk, lb=0, vtype=GRB.INTEGER, name="z")
    a = model.addVars(ell, lb=0, vtype=GRB.CONTINUOUS, name="a")
    lambda1 = model.addVar(name="lambda1", vtype=GRB.CONTINUOUS)
    lambda2 = model.addVar(name="lambda2", vtype=GRB.CONTINUOUS)
    lambda3 = model.addVars(ell, lb=0, vtype=GRB.CONTINUOUS, name='lambda3')
    lambda4 = model.addVar(name="lambda4", vtype=GRB.CONTINUOUS)

    M = INFINITY
    model.setParam("IntFeasTol", 1e-9)

    # Constraints
    # Lambda
    if livestock != 'ckn-layers':
        for i in range(ell):
            if Hi[i] == -1:
                continue
            model.addConstr(gp.quicksum(h[i, f, g] 
                for f in range(Fi[i]) for g in subtypes) - Hi[i]<=lambda1)
            model.addConstr(gp.quicksum(h[i, f, g] 
                for f in range(Fi[i]) for g in subtypes) - Hi[i]>=-lambda1)
    else:
        H = hdf['all'].values # only total population available
        if H != -1:
            model.addConstr(gp.quicksum(h[i, f, g] 
                for i in range(ell) for f in range(Fi[i]) for g in subtypes) 
                - H<=lambda1)
            model.addConstr(gp.quicksum(h[i, f, g] 
                for i in range(ell) for f in range(Fi[i]) for g in subtypes) 
                - H>=-lambda1)

    # Category farm size constraint
    for i in range(ell):
        for f in range(Fi[i]):
            model.addConstr(gp.quicksum(h[i,f,g] for g in subtypes) >= Wmin[i], 
                    f"Lower bound on farm size")
            model.addConstr(gp.quicksum(h[i,f,g] for g in subtypes) <= Wmax[i], 
                    f"Upper bound on farm size")

    # Subtype farm category constraints: Farm counts.
    # Constraints to set xfigk.
    for i in range(ell):
        for f in range(Fi[i]):
            for g in subtypes:
                for k in range(ell):
                    model.addConstr(h[i,f,g] >= Wmin[k]-(1-x[i,f,g,k])*M, 
                            f"Lower bound constraint for x{f}{i}{g}{k}")
                    model.addConstr(h[i,f,g] <= Wmax[k]+(1-x[i,f,g,k])*M, 
                            f"Upper bound constraint for x{f}{i}{g}{k}")
                    model.addConstr(h[i,f,g] >= (1-y[i,f,g,k]), 
                            f"Upper bound constraint for y{f}{i}{g}{k}")
                    model.addConstr(h[i,f,g] <= (1-y[i,f,g,k])*M, 
                            f"Upper bound constraint for y{f}{i}{g}{k}")

    # A farm can belong to exactly one category
    for i in range(ell):
        for f in range(Fi[i]):
            for g in subtypes:
                model.addConstr(gp.quicksum(x[i, f, g, k] 
                    for k in range(ell))+y[i,f,g,k] == 1, 
                    "sum_to_one_category[{i}{f}{g}]")

    # Farm counts corresponding to subtype farm category
    for g in subtypes:
        for k in range(ell):
            model.addConstr(gp.quicksum(x[i,f,g,k] for i in range(ell) 
                for f in range(Fi[i]))==Fgk[g][k], 
                f"FarmCountSubtype[{g},{k}]")

    # Subtype farm category constraints: Population counts.
    # Constraints to set xfigk.
    for i in range(ell):
        for f in range(Fi[i]):
            for g in subtypes:
                for k in range(ell):
                    model.addConstr(z[i,f,g,k] <= h[i,f,g], 
                            f"Sets upper bound for z{f}{i}{g}{k}.")
                    model.addConstr(z[i,f,g,k] <= x[i,f,g,k]*M, 
                            f"Forces z{f}{i}{g}{k}=0 when x{f}{i}{g}{k}=0")
                    model.addConstr(z[i,f,g,k] >= h[i,f,g] - (1-x[i,f,g,k])*M, 
                            f"Forces z{f}{i}{g}{k}=h{f}{i}{g} when x{f}{i}{g}{k}=1")

    # Subtype distribution: Minimize number of subtypes per farm
    for i in range(ell):
        for f in range(Fi[i]):
                model.addConstr(gp.quicksum(x[i, f, g, k] 
                    for g in subtypes for k in range(ell)) <= lambda2, 
                    "lambda2 constraint")

    # Match total population distribution in each category
    if livestock != 'ckn-layers':
        for g in subtypes:
            for k in range(ell):
                model.addConstr(gp.quicksum(z[i,f,g,k] for i in range(ell) 
                    for f in range(Fi[i]))-Hgk[g][k]<=lambda4, 
                    f"HeadCountSubtype[{g},{k} upper bound]")
                model.addConstr(gp.quicksum(z[i,f,g,k] for i in range(ell) 
                    for f in range(Fi[i]))-Hgk[g][k]>=-lambda4, 
                    f"HeadCountSubtype[{g},{k} lower bound]")
    else:
        for g in subtypes:  # there is only one subtype 'dummy'
            model.addConstr(gp.quicksum(z[i,f,g,k] for i in range(ell) 
                for f in range(Fi[i]) for k in range(ell))==Hgk[g], 
                    f"HeadCountSubtypeTotal[{g}]")

    # Equitable distribution in each category
    for i in range(ell):
        model.addConstr(gp.quicksum(h[i,f,g]/Fi[i] for f in range(Fi[i])
            for g in subtypes)==a[i],
            f"Average population in each farm category")

    for i in range(ell):
        for f in range(Fi[i]):
            model.addConstr(gp.quicksum(h[i, f, g] 
                for g in subtypes) - a[i]<=lambda3[i])
            model.addConstr(gp.quicksum(h[i, f, g] 
                for g in subtypes) - a[i]>=-lambda3[i])

    # Set objective
    ng = len(subtypes)
    model.setObjective(0.0001*(
            lambda1 +
            (tot_heads+1)*lambda2 +
            (tot_heads+1)*(ng+1)*gp.quicksum(lambda3[i] for i in range(ell)) +
            100*(tot_heads+1)**2*(ng+1)*lambda4), GRB.MINIMIZE)
    ## model.setObjective(0.0001*(
    ##         lambda1 +
    ##         (tot_heads+1)*lambda2 +
    ##         (tot_heads+1)*(ng+1)*gp.quicksum(lambda3[i] for i in range(ell)) +
    ##         100000*lambda4), GRB.MINIMIZE)

    # Optimize model
    try:
        print(f'Setting threads to SLURM_NTASKS')
        model.Params.Threads=int(environ['SLURM_NTASKS'])
    except:
        print(f'Failed to set threads to SLURM_NTASKS')
        pass
    model.setParam('TimeLimit', TIME_LIMIT) 
    ## tolerance = max(hdf[subtypes].sum().sum()*GF_OPT_TOL_PERC/100, 
    ##         GF_OPT_TOL_MAX)
    tolerance = hdf[subtypes].sum().sum()*GF_OPT_TOL_PERC/100
    print('Tolerance:', tolerance)
    stats.gf_opt_tol = tolerance
    stats.gf_opt_tol_perc = GF_OPT_TOL_PERC
    # stats.gf_opt_tol_max = GF_OPT_TOL_MAX
    model.setParam('MIPGapAbs', tolerance)

    model.optimize()

    # Extract the results
    farms_tuples = []
    x_tuples = []
    y_tuples = []
    z_tuples = []

    if model.SolCount > 0:
        if model.status == GRB.OPTIMAL:
            stats.gf_sol = 'optimal'
            print("Optimal solution found")
        else:
            print('Timed out. No optimal solution found. Reporting best solution.')
            stats.gf_sol = 'non-optimal'
        for i in range(ell):
            for f in range(Fi[i]):
                for g in subtypes:
                    farms_tuples.append((i, f, g, h[i,f,g].X))
                    for k in range(ell):
                        x_tuples.append((i, f, g, k, x[i,f,g,k].X))
                        y_tuples.append((i, f, g, k, y[i,f,g,k].X))
                        z_tuples.append((i, f, g, k, z[i,f,g,k].X))
        stats.lambda1 = lambda1.X
        stats.lambda2 = lambda2.X
        stats.lambda4 = lambda4.X
        print(f'lambda1: {stats.lambda1}, lambda2: {stats.lambda2}, lambda4: {stats.lambda4}')
    else:
        stats.gf_sol = 'failed'
        return -1

    farms = pd.DataFrame(farms_tuples, columns=['cat', 'farm', 'subtype', 'heads'])
    xdf = pd.DataFrame(x_tuples, columns=['cat', 'farm', 'subtype', 'scat', 
        'value'])
    ydf = pd.DataFrame(y_tuples, columns=['cat', 'farm', 'subtype', 'scat', 
        'value'])
    zdf = pd.DataFrame(z_tuples, columns=['cat', 'farm', 'subtype', 'scat', 
        'value'])

    ## with open('con.txt', 'w') as f:
    ##     for constr in model.getConstrs():
    ##         f.write(f"Constraint Name: {constr.ConstrName}, Sense: {constr.Sense}, RHS: {constr.RHS}")

    tdf = farms.groupby(['cat', 'farm'])['heads'].sum().reset_index()
    tdf['subtype'] = 'all'
    farms = pd.concat([farms, tdf], ignore_index=True)
    farms = farms[farms.heads!=0].copy()
    farms['derived_cat'] = farms.heads.apply(assign_category, args=[Wmin, Wmax])

    hdf_ = farms[['subtype', 'heads', 'derived_cat']].groupby(
            ['subtype', 'derived_cat']).sum().reset_index().pivot(
                    index=['derived_cat'], columns='subtype',
                    values='heads').reset_index().fillna(0)
    fdf_ = farms[['subtype', 'heads', 'derived_cat']].groupby(
            ['subtype', 'derived_cat']).count().reset_index().pivot(
                    index=['derived_cat'], columns='subtype',
                    values='heads').reset_index().fillna(0)

    if livestock != 'ckn-layers':
        if not stats.lambda4:
            if abs(hdf[subtypes] - hdf_[subtypes]).sum().sum():
                raise ValueError('Mismatch of aggregated heads.')
        if abs(fdf[subtypes] - fdf_[subtypes]).sum().sum():
            raise ValueError('Mismatch of aggregated farms.')
    else:
        H_ = hdf_.dummy.sum()
        if H_ != Hgk['dummy']:
            raise ValueError('Mismatch of aggregated heads.')

    fmap = farms[['cat', 'farm']].drop_duplicates().sort_values(
            ['cat', 'farm']).reset_index(drop=True).reset_index().rename(
                    columns={'index': 'fid'})
    farms = farms.merge(fmap, on=['cat', 'farm'])
    farms = farms[['fid', 'subtype', 'heads']]
    
    return farms

def farms_to_cells(farms, cells, stats):
    heads = farms[farms.subtype=='all'][['fid', 'heads']].sort_values('fid')
    set_trace()
    H = heads.heads.values
    Q = cells.val.values

    # Normalize Q
    Q = H.sum()/Q.sum() * Q

    # Parameters
    N_f = len(H)  # Number of farms
    N_c = len(Q)  # Number of cells

    # Create a Gurobi model
    model = gp.Model()

    # Variables:
    x = model.addVars(N_f, N_c, vtype=GRB.BINARY, name="x")
    h = model.addVars(N_f, N_c, vtype=GRB.INTEGER, name="h")
    lambda5 = model.addVar(lb=0, vtype=GRB.INTEGER, name="lambda5")

    # Objective: 
    model.setObjective(lambda5, GRB.MINIMIZE)

    # Constraints:
    for i in range(N_f):
        for j in range(N_c):
            model.addConstr(h[i,j]==H[i]*x[i,j], name=f"h_{i}_{j}_constraint")

    # 2. Each farm is assigned to exactly one cell
    for i in range(N_f):
        model.addConstr(gp.quicksum(x[i,j] for j in range(N_c)) == 1, 
                name=f"farm_assignment_{i}")

    # 3. The difference between the heads assigned to each cell and the 
    # required heads is within lambda5
    for j in range(N_c):
        model.addConstr(gp.quicksum(h[i,j] for i in range(N_f))-Q[j] <= lambda5)
        model.addConstr(gp.quicksum(h[i,j] for i in range(N_f))-Q[j] >= -lambda5)

    # Optimize model
    model.setParam('TimeLimit', TIME_LIMIT) 
    try:
        print(f'Setting threads to SLURM_NTASKS')
        model.Params.Threads=int(environ['SLURM_NTASKS'])
    except:
        print(f'Failed to set threads to SLURM_NTASKS')
        pass

    tolerance = max(FC_OPT_TOL_PERC*H.sum()/100, FC_OPT_TOL_MAX)
    print('Tolerance:', tolerance)
    stats.fc_opt_tol = tolerance
    model.setParam('MIPGapAbs', tolerance)
    model.optimize()

    # Display results
    if model.SolCount > 0:
        if model.status == GRB.OPTIMAL:
            stats.fc_sol = 'optimal'
            print("Optimal solution found")
        else:
            print('Timed out. No optimal solution found. Reporting best solution.')
            stats.fc_sol = 'non-optimal'
        stats.lambda5 = lambda5.X
        print(f'lambda5: {stats.lambda5}')
        cell_var = []
        for i in range(N_f):
            for j in range(N_c):
                if h[i,j].X:
                    cell_var.append((i,j,h[i,j].X))
        assg = pd.DataFrame.from_records(cell_var, 
                columns=['fid', 'cell', 'heads'])
        cellmap = cells[['x', 'y']].reset_index(drop=True)
        assg['x'] = assg.cell.map(cellmap.x)
        assg['y'] = assg.cell.map(cellmap.y)
        return assg
    else:
        print('Failed.')
        stats.fc_sol = 'failed'
        return -1

# This correlation should probably computed separately. This is just legacy.
def correlation(farms, glw, stats):
    corr_vec = farms[farms.subtype=='all'][['x', 'y', 'heads']].copy()
    corr_vec = corr_vec.groupby(['x', 'y']).sum()
    corr_vec = corr_vec.merge(glw[['x', 'y', 'val']], on=['x', 'y'])

    if corr_vec.shape[0] == 1:
        stats.corr = 1
        stats.pval = -1
    else:
        pr = pearsonr(corr_vec.val, corr_vec.heads)
        stats.corr = pr.statistic
        stats.pval = pr.pvalue
        print(f'Pearson: {stats.corr}, {stats.pval}')

def main():
    # parser
    parser=argparse.ArgumentParser(description=DESC, 
    formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-s', '--state', type=int, required=True, help='State FIPS')
    parser.add_argument('-c', '--county', type=int, required=True, help='County FIPS')
    parser.add_argument('-t', '--type', required=True)
    args = parser.parse_args()

    start = time()

    # Load datasets
    df = pd.read_csv('../results/agcensus_filled_gaps.csv.zip')
    df = df.astype({'state_code': 'int', 'county_code': 'int', 'value': 'int'})

    glw = pd.read_csv('../../data/glw/glw_livestock.csv.zip')
    glw = glw.astype({'state_code': 'int', 'county_code': 'int'})

    # Assign per county,livestock
    stats = Stats()
    stats.livestock = args.type
    stats.state = args.state
    stats.county = args.county
    loc_df = df[(df.county_code==args.county) & 
            (df.state_code==args.state) &
            (df.livestock==args.type)]
    loc_glw = glw[(glw.state_code==args.state) &
            (glw.county_code==args.county) & 
            (glw.livestock==GLW_MAP[args.type])].copy()
    print(stats.state, stats.county, stats.livestock)

    stats_out_file = \
            f'stats_farms_to_cells_{stats.state}_{stats.county}_{stats.livestock}.csv'

    # Prepare input
    heads = loc_df[loc_df.unit=='heads']
    farms = loc_df[loc_df.unit=='operations']

    # No fields to be assigned, no problem
    stats.farms_to_be_assigned = True
    if not farms.shape[0]: 
        stats.farms_to_be_assigned = False
        print(f'No farms found.')
        print(f'Total time: {stats.state},{stats.county},{stats.livestock},{(time()-start)//60}')
        generate_stats([stats], out=stats_out_file)
        return

    # No cells to assign to, assign uniformly
    stats.uniform = False
    if loc_glw.val.sum() == 0 and farms.shape[0]: 
        stats.uniform = True
        loc_glw = glw[(glw.state_code==args.state) & 
                (glw.county_code==args.county)][
                ['x', 'y', 'state_code', 'county_code']].drop_duplicates()
        loc_glw['livestock'] = args.type
        loc_glw['val'] = 1

    proc_start = time()

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
    if 'all' not in hdf.columns:
        hdf['all'] = -1
        stats.filled_all_column = True
    else:
        stats.filled_all_column = False

    # Generate farms
    farm_assg = generate_farms(hdf, fdf, stats, stats.livestock)
    if stats.gf_sol == 'failed':
        generate_stats([stats], out=stats_out_file)
        return
    gf_time = time()
    stats.gf_time = gf_time - proc_start

    # Assign cells to farms
    cell_assg = farms_to_cells(farm_assg, loc_glw, stats)
    if stats.fc_sol == 'failed':
        generate_stats([stats], out=stats_out_file)
        return

    stats.fc_time = time() - gf_time
    odf = farm_assg.merge(cell_assg[['fid', 'x', 'y']], on='fid')
    odf['state_code'] = stats.state
    odf['county_code'] = stats.county
    odf['livestock'] = stats.livestock
    
    odf = odf.astype({'heads': 'int'})

    # Correlation with GLW
    correlation(odf, loc_glw, stats)

    # Remove dummy columns
    odf = odf[odf.subtype!='dummy']

    generate_stats([stats], out=stats_out_file)

    odf.to_csv(
            f'farms_to_cells_{stats.state}_{stats.county}_{stats.livestock}.csv.zip', 
            index=False)

    print(f'Total time: {stats.state},{stats.county},{stats.livestock},{(time()-start)//60}')

    print('Done')

if __name__ == '__main__':
    main()
