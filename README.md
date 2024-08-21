# PTSA

## Description
`AbstractSA.py` provides two SA interfaces:
An abstract Simulated Annealing solver.
An abstract Parallel Tempering Simulated Annealing solver with MPI.

The user only need to specify the trasition function.
(Why? Because there can be many rules / constraints for the transition and the next state.)

## Dependencies
- `numpy`
- `pandas`: only if you do postprocessing of `output.log`
- 'mpi4py': only if you need PTSA
- `pickle`: only if you want to save as pickle files

## Usage
See `example.py`
