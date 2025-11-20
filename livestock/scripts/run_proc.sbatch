#!/bin/bash
# SLURM JOB SCRIPT OPTIONS:
#SBATCH --time=06:00:00

#SBATCH -N 1
#SBATCH -n 10
#SBATCH --mem 80G

# Set the partition to submit to (a partition is equivalent to a queue)
#SBATCH -p bii
#SBATCH --qos bii-half

# charge code
##SBATCH -A nssac_students
#SBATCH -A bii_nssac

# Load any modules you require:
source /sfs/gpfs/tardis/home/aa5ts/miniforge3/etc/profile.d/conda.sh
conda activate /project/bii_nssac/people/aa5ts/conda-envs/ldt

echo "###################################"
echo "$command"
echo "###################################"
eval "$command"
