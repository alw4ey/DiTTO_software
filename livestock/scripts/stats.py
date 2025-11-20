DESC='''
For gathering statistics.
'''

import pandas as pd
from pdb import set_trace

class Stats():
    def __init__(self):
        pass

    def display(self):
        for x in dir(self): 
            if x[0:2] != '__' and  x != 'display':
                print(x, getattr(self,x))

def generate_stats(stats_list, mode='file', out=None):
    sdict_list = []
    for stats in stats_list:
        sdict_list.append({x: getattr(stats,x) for x in dir(stats) if x[0:2] != '__' and x != 'display'})

    df = pd.DataFrame.from_records(sdict_list)
    
    if mode == 'file': 
        df.to_csv(out, index=False)
        return
    elif mode == 'dataframe':
        return df
    else:
        raise ValueError('Mode can be either file/dataframe.')


