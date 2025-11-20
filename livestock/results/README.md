# Farm/population distribution data format
File: ``farms_to_cells.csv.zip``

```
fid,subtype,heads,x,y,state_code,county_code,livestock
0,beef,1,1055,596,29,199,cattle
0,other,1,1055,596,29,199,cattle
0,all,2,1055,596,29,199,cattle
1,beef,1,1056,595,29,199,cattle
1,all,1,1056,595,29,199,cattle
2,other,1,1055,594,29,199,cattle
2,all,1,1055,594,29,199,cattle
3,beef,1,1056,594,29,199,cattle
3,other,1,1056,594,29,199,cattle
3,all,2,1056,594,29,199,cattle
```

``fid``: Farm ID (unique for a given county)<br>
``subtype``: Livestock subtype
``heads``: Number of heads
``x,y``: as in GLW data.<br>
``state_code``: State FIPS code<br>
``county_code``: County FIPS code<br>
``livestock``<br>
