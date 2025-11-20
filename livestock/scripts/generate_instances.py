DESC='''
Generate instances for farm to cell assignment.

By AA
'''

import pandas as pd
import os
from pdb import set_trace
import stat

SKIP_INSTANCE = 'optimal'

def main():
    agcensus = pd.read_csv(
            '../results/agcensus_filled_gaps.csv.zip')
    agcensus = agcensus.astype({'state_code': 'int', 'county_code': 'int'})
    agcensus = agcensus[agcensus.state!='alaska']
    #agcensus = agcensus[agcensus.livestock=='poultry']
    instances = agcensus[['state_code', 'county_code', 'livestock']
            ][agcensus.county_code!=-1].drop_duplicates()
    print(f'Total Number of instances: {instances.shape[0]}')

    try:
        stats = pd.read_csv('../results/stats_farms_to_cells.csv.zip')
        stats.loc[stats.livestock=='poultry', 'livestock'] = stats[
                stats.livestock=='poultry'].subtype.values
        print('Some spurious files needed to be handled. Check if the problem persists.')
        stats = stats[~stats.county.isnull()]
        stats = stats[stats.county!='False']
        stats = stats.astype({'county': 'float'})

        instances = instances.merge(stats, 
                left_on=['state_code', 'county_code', 'livestock'],
                right_on=['state', 'county', 'livestock'], how='left')
        ## instances = instances[(instances.gf_sol!='optimal') & (~instances.gf_sol.isnull())]
        ## instances = instances[(instances.lambda4!=0) & (~instances.lambda4.isnull())]
        instances = instances[(instances.gf_sol.isnull()) | 
                (instances.gf_sol=='failed') |
                (instances.fc_sol=='failed')]
        ## instances = instances[(instances.gf_sol!='optimal') |
        ##         (instances.fc_sol!='optimal') | 
        ##         (instances.gf_sol=='failed') |
        ##         (instances.fc_sol=='failed')]
        print('Found stats file. Revised instances', instances.shape[0])
    except FileNotFoundError:
        print('No stats file found.')

    with open('run', 'w') as f:
        count = 0
        for i, row in enumerate(instances.values):
            state = row[0]
            county = row[1]
            livestock = row[2]

            if i>10000000:
                break
            ## if os.path.exists(f'farms_to_cells_{state}_{county}_{livestock}.csv.zip'):
            ##     print(f'Skipping {state}-{county} as file exists ...')
            ##     ## if SKIP_NON_OPTIMAL or stats[(stats.statefp==state) &
            ##     ##         (stats.countyfp==county)].optimal_sol.prod():
            ##     ##     continue
            ##     continue
            count+=1
            f.write(f'''sbatch \
-o log_{state}_{county}_{livestock} \
--export=ALL,command=\"python ../scripts/farms_to_cells.py -s {state} -c {county} -t {livestock}\" \
-J {state}-{county}-{livestock} \
../scripts/run_proc.sbatch; \
../scripts/qreg\n''') # hardcoded; should change later
        print(f'Instances to run: {count}')
    os.chmod('run', os.stat('run').st_mode | stat.S_IXUSR)

if __name__ == '__main__':
    main()

