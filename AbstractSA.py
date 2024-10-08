import copy
import numpy as np
from abc import ABC, abstractmethod

import pandas as pd
from mpi4py import MPI
from pathlib import Path
import logging


class SA(ABC):
    """
    Abstract base class for Simulated Annealing (SA) algorithm.
    """

    def __init__(self, task_name: str, obj, x0, params, T_i: float, T_f: float, decay: float, reps: int, iters: int,
                 verbose: int, output: Path):
        """
        Initializes the simulated annealing algorithm with the given parameters.
        """
        self.task_name = task_name
        self.obj = obj
        self.x0 = x0
        self.params = params
        self.x = copy.deepcopy(x0)
        self.y: int = obj(x0)
        self.best_x = copy.deepcopy(x0)
        self.best_y: float = self.y
        self.T_i: float = T_i
        self.T_f: float = T_f
        self.T: float = T_i
        self._reps: int = reps
        self._iters: int = iters
        self._decay: float = decay
        self._verbose: int = verbose
        self._output: Path = output

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,  # Set the logging level
            format='%(message)s',  # Log message format
            handlers=[
                logging.StreamHandler(),  # Print to terminal
                logging.FileHandler(f"{self.task_name}_output.log")  # Print to file
            ],
            # filemode="w"
        )

        self._logger = logging.getLogger()

    def __repr__(self):
        return f"""
        Simulated Annealing Solver:
        Initial temperature: {self.T_i:>10.6f}
        Final temperature  : {self.T_f:>10.6f}
        Temperature decay  : {self._decay:>10.6f}
        Outer iterations   : {self._iters:>10d}
        Inner iterations   : {self._reps:>10d}
        """

    def step(self):
        """
        Perform a single step of the simulated annealing algorithm.
        This method should be overridden to implement the specific logic of a step.
        """
        if self._verbose == 2:
            self._logger.info("=" * 46)
            self._logger.info(f"{'Iter':>6} | {'°C':>10} | {'Trial Loss':>10} | {'Best Loss':>10}")
            self._logger.info("=" * 46)

        for i in range(self._reps):
            x_new = self.transition()
            y_new = self.obj(x_new)
            df = y_new - self.y

            if df < 0 or np.exp(-df / self.T) > np.random.rand():
                self.x, self.y = x_new, y_new
                if y_new < self.best_y:
                    self.best_x, self.best_y = copy.deepcopy(x_new), copy.deepcopy(y_new)

            if i % 10 == 0 and self._verbose == 2:
                self._logger.info(f"{i:>6d} | {self.T:>11f} | {self.y:>10.2f} | {self.best_y:>10.2f}")

    @abstractmethod
    def transition(self):
        """
        Transition to a new state based on the current state and temperature.
        This method should be overridden to define how the algorithm transitions between states.
        """
        pass

    def cool_down(self):
        """
        Update the temperature according to the cooling schedule.
        """
        self.T *= self._decay

    def run(self, ):
        """
        Execute the simulated annealing process for a specified number of iterations.
        """
        while self.T > self.T_f:
            self.step()
            self.cool_down()

        return self.best_x, self.best_y


class PTSA(SA, ABC):
    def __init__(self, task_name: str, obj, x0, params, T_i: float, T_f: float, decay: float,
                 reps: int, iters: int, verbose: int, output: Path, theta: float):
        super().__init__(task_name, obj, x0, params, T_i, T_f, decay, reps, iters, verbose, output)
        self.theta = theta
        self.rank = 0

    def __repr__(self):
        return f"""
        Parallel Tempering Simulated Annealing Solver:
                 (This is rank {self.rank})
        Initial temperature: {self.T_i:>10.6f}
        Final temperature  : {self.T_f:>10.6f}
        Temperature decay  : {self._decay:>10.6f}
        Outer iterations   : {self._iters:>10d}
        Inner iterations   : {self._reps:>10d}
        Change temperature : {self.theta*100:10.1f}%
        """

    def step(self):
        if self._verbose == 2 and self.rank == 0:
            self._logger.info("=" * 55)
            self._logger.info(f"{'Iter':>6} | {'°C':>10} | {'Trial Loss':>10} | {'Rank':>6} | {'Best Loss':>10}")
            self._logger.info("=" * 55)
        MPI.COMM_WORLD.Barrier()

        for i in range(self._reps):
            x_new = self.transition()
            y_new = self.obj(x_new)
            df = y_new - self.y

            if df < 0 or np.exp(-df / self.T) > np.random.rand():
                self.x, self.y = x_new, y_new
                if y_new < self.best_y:
                    self.best_x, self.best_y = copy.deepcopy(x_new), copy.deepcopy(y_new)

            if i % 10 == 0 and self._verbose == 2:
                self._logger.info(f"{i:>6d} | {self.T:>11f} | {self.y:>10.2f} | {self.rank:>6d} | {self.best_y:>10.2f}")

    def run(self):
        COMM = MPI.COMM_WORLD
        RANK = COMM.Get_rank()
        SIZE = COMM.Get_size()
        self.rank = RANK
        ##=================PTSA loop=================##
        it = 0
        while it < self._iters:
            self.step()  # new x, y, best_x, best_y have been updated
            data = [self.T, self.best_y, self.rank]
            msg = COMM.gather(data, root=0)
            if RANK == 0:
                self._logger.info("=" * 41)
                self._logger.info(f"{'Rank':>6} | {'Iter':>6} | {'°C':>10} | {'Loss':>10}")
                self._logger.info("=" * 41)
                best_rank = np.argmin(np.array([_[1] for _ in msg]))
                if self._verbose == 1:
                    for i in range(SIZE):
                        marker = (i == best_rank) * " **"
                        self._logger.info(f"{msg[i][2]:>6d} | {it + 1:>6d} | {msg[i][0]:>10.6f} | {msg[i][1]:>10.4f}{marker}")
                elif self._verbose == 0:
                    self._logger.info(
                        f"{msg[best_rank][2]:>6d} | {it + 1:>6d} | {msg[best_rank][0]:>10.6f} | {msg[best_rank][1]:>10.4f}")
                else:
                    pass

                T = [msg[i][0] for i in range(SIZE)]
                fx = [msg[i][1] for i in range(SIZE)]

                index = np.argsort(T)
                for i in range(SIZE - 1):
                    sol1 = index[i]
                    sol2 = index[i + 1]
                    if np.random.random() > self.theta:
                        accept_rate = np.exp(-fx[sol2] / T[sol1] - fx[sol1] / T[sol2] + fx[sol2] / T[sol2] + fx[sol1] / T[sol1])
                        if accept_rate > np.random.random():
                            T[sol1], T[sol2] = T[sol2], T[sol1]
                            # index[i], index[i + 1] = index[i + 1], index[i]
                data = T
            else:
                data = None

            it += 1
            self.T = COMM.scatter(data, root=0)
            self.cool_down()

            # break
            save_name = self._output / f"rank_{self.rank}_{self.task_name}_best_x.pkl"
            save_var(save_name, self.best_x)

        return self.best_x, self.best_y

    def process_output(self, SIZE: int):
        df = pd.DataFrame(columns=[f"Rank{i}" for i in range(SIZE)])
        outfile = Path(f"{self.task_name}_output.log")
        iter = 0
        with open(outfile, 'r') as f:
            while f.readline():
                iter += 1
                f.readline()
                f.readline()
                for i in range(SIZE):
                    line = f.readline()
                    info = [_.strip() for _ in line.split('|')]
                    df.loc[iter, f"Rank{i}"] = info[3]
        df.to_csv(outfile.name[:-4] + ".csv")



def save_var(filename, action_trees_sa):
    with open(filename, "wb") as f:
        pk.dump(action_trees_sa, f)


def load_var(filename):
    with open(filename, "rb") as f:
        return pk.load(f)
