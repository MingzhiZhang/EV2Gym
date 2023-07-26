'''
===================================
Author: Stavros Orfanoudakis 2023
===================================
'''

import gym
from gym import spaces
import numpy as np
import datetime
import pickle

from .grid import Grid
from .ev_charger import EV_Charger
from .ev import EV
from .transformer import Transformer
from .replay import EvCityReplay


class EVCity(gym.Env):
    '''
    This file contains the EVCity class, which is used to represent the environment of the city.
    '''

    def __init__(self,
                 cs=None,
                 load_prices_from_replay=False,
                 load_ev_from_replay=False,
                 load_from_replay_path=None,
                 empty_ports_at_end_of_simulation=True,
                 simulate_grid=False,
                 generate_rnd_game=False,  # generate a random game without terminating conditions
                 case='default',
                 number_of_ports_per_cs=2,
                 number_of_transformers=1,
                 score_threshold=1,
                 timescale=5,
                 date=(2023, 7, 21),  # (year, month, day)
                 hour=(18, 0),  # (hour, minute) 24 hour format
                 save_replay=True,
                 verbose=False,
                 simulation_length=1000):

        super(EVCity, self).__init__()

        print(f'Initializing EVCity environment...')

        self.generate_rnd_game = generate_rnd_game
        self.load_from_replay_path = load_from_replay_path
        self.load_ev_from_replay = load_ev_from_replay
        self.load_prices_from_replay = load_prices_from_replay
        self.empty_ports_at_end_of_simulation = empty_ports_at_end_of_simulation
        self.save_replay = save_replay
        self.verbose = verbose  # Whether to print the simulation progress or not
        self.simulation_length = simulation_length

        if load_from_replay_path is not None:
            with open(load_from_replay_path, 'rb') as file:
                self.replay = pickle.load(file)

            # self.save_replay = False
            self.sim_date = self.replay.sim_date
            self.simulate_grid = self.replay.simulate_grid
            self.timescale = self.replay.timescale
            # self.simulation_length = self.replay.sim_length
            self.cs = self.replay.n_cs
            self.number_of_transformers = self.replay.n_transformers
            self.score_threshold = self.replay.score_threshold
            self.number_of_ports_per_cs = self.replay.max_n_ports

        else:
            assert cs is not None, "Please provide the number of charging stations"
            self.cs = cs  # Number of charging stations
            # Threshold for the user satisfaction score
            self.score_threshold = score_threshold
            self.number_of_ports_per_cs = number_of_ports_per_cs
            self.number_of_transformers = number_of_transformers
            # Timescale of the simulation (in minutes)
            self.timescale = timescale
            self.simulation_length = simulation_length
            # Simulation time
            self.sim_date = datetime.datetime(date[0],
                                              date[1],
                                              date[2],
                                              hour[0],
                                              hour[1])

            self.simulate_grid = simulate_grid  # Whether to simulate the grid or not

        self.sim_name = f'ev_city_{self.simulation_length}_' + \
            f'{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")}'

        # Simulate grid
        if self.simulate_grid:
            self.grid = Grid(charging_stations=cs, case=case)
            self.cs_buses = self.grid.get_charging_stations_buses()
            self.cs_transformers = self.grid.get_bus_transformers()
        else:
            self.cs_buses = [None] * cs
            self.cs_transformers = np.random.randint(
                self.number_of_transformers, size=cs)

        # Instatiate Transformers
        self.transformers = self._load_transformers()

        # Instatiate Charging Stations
        self.charging_stations = self._load_ev_charger_profiles()

        # Instatiate EV profiles if they exist
        self.ev_profiles = self._load_ev_profiles()

        # Load Electricity prices for every charging station
        self.charge_prices, self.discharge_prices = self._load_electricity_prices()

        # Action space: is a vector of size "Sum of all ports of all charging stations"
        self.number_of_ports = np.array(
            [cs.n_ports for cs in self.charging_stations]).sum()
        self.action_space = spaces.Box(
            low=-1, high=1, shape=(self.number_of_ports, 1), dtype=np.float32)

        # Observation space: is a matrix of size ("Sum of all ports of all charging stations",n_features)
        n_features = 5
        self.observation_space = (self.number_of_ports, n_features)
        # TODO: Observation space is different when simulating the grid

        # Observation mask: is a vector of size ("Sum of all ports of all charging stations") showing in which ports an EV is connected
        self.observation_mask = np.zeros(self.number_of_ports)

        self.current_step = 0
        self.total_evs_spawned = 0

        self.current_ev_departed = 0
        self.current_ev_arrived = 0
        self.current_evs_parked = 0

        self.done = False

        if self.save_replay:
            self.EVs = []  # Store all of the EVs in the simulation that arrived

    def _load_transformers(self):
        '''Loads the transformers of the simulation
        If load_from_replay_path is None, then the transformers are created randomly

        Returns:
            - transformers: a list of transformer objects'''

        transformers = []
        if self.load_from_replay_path is None:
            for i in range(self.number_of_transformers):
                transformer = Transformer(id=i,
                                          cs_ids=np.where(self.cs_transformers == i)[0])
                transformers.append(transformer)
        else:
            transformers = self.replay.transformers

        return transformers

    def _load_ev_charger_profiles(self):
        '''Loads the EV charger profiles of the simulation
        If load_from_replay_path is None, then the EV charger profiles are created randomly

        Returns:
            - ev_charger_profiles: a list of ev_charger_profile objects'''

        charging_stations = []
        if self.load_from_replay_path is None:
            for i in range(self.cs):
                ev_charger = EV_Charger(id=i,
                                        connected_bus=self.cs_buses[i],
                                        connected_transformer=self.cs_transformers[i],
                                        n_ports=self.number_of_ports_per_cs,
                                        timescale=self.timescale,
                                        verbose=self.verbose,)

                charging_stations.append(ev_charger)
            return charging_stations

        return self.replay.charging_stations

    def _load_ev_profiles(self):
        '''Loads the EV profiles of the simulation
        If load_from_replay_path is None, then the EV profiles are created randomly

        Returns:
            - ev_profiles: a list of ev_profile objects'''

        if self.load_from_replay_path is None:
            return None
        elif self.load_ev_from_replay:
            return self.replay.EVs

    def _load_electricity_prices(self):
        '''Loads the electricity prices of the simulation
        If load_from_replay_path is None, then the electricity prices are created randomly

        Returns:
            - charge_prices: a matrix of size (number of charging stations, simulation length) with the charge prices
            - discharge_prices: a matrix of size (number of charging stations, simulation length) with the discharge prices'''

        if self.load_from_replay_path is None or not self.load_prices_from_replay:
            charge_prices = np.random.normal(
                -0.05, 0.05, size=(self.cs, self.simulation_length))
            charge_prices = -1 * np.abs(charge_prices)
            discharge_prices = np.random.normal(
                0.1, 0.05, size=(self.cs, self.simulation_length))
            discharge_prices = np.abs(discharge_prices)
            return charge_prices, discharge_prices

        return self.replay.charge_prices, self.replay.discharge_prices

    def reset(self):
        '''Resets the environment to its initial state'''
        self.current_step = 0
        # Reset all charging stations
        for cs in self.charging_stations:
            cs.reset()

        return self._get_observation()

    def step(self, actions, visualize=False):
        ''''
        Takes an action as input and returns the next state, reward, and whether the episode is done
        Inputs:
            - actions: is a vector of size "Sum of all ports of all charging stations taking values in [-1,1]"
        Returns:
            - observation: is a matrix with the complete observation space
            - reward: is a scalar value representing the reward of the current step
            - done: is a boolean value indicating whether the episode is done or not
        '''
        assert not self.done, "Episode is done, please reset the environment"
        total_costs = 0
        user_satisfaction_list = []

        self.current_ev_departed = 0
        self.current_ev_arrived = 0

        port_counter = 0

        # Reset current power of all transformers
        for tr in self.transformers:
            tr.current_power = 0

        # Call step for each charging station and spawn EVs where necessary
        for cs in self.charging_stations:
            n_ports = cs.n_ports
            costs, user_satisfaction = cs.step(
                actions[port_counter:port_counter + n_ports],
                self.charge_prices[cs.id, self.current_step],
                self.discharge_prices[cs.id, self.current_step])

            for u in user_satisfaction:
                user_satisfaction_list.append(u)

            self.transformers[cs.connected_transformer].step(
                cs.current_power_output)

            total_costs += costs
            self.current_ev_departed += len(user_satisfaction)

            port_counter += n_ports

            # Spawn EVs
            if self.ev_profiles is None:
                max_stay_of_ev = 15
                if max_stay_of_ev > self.simulation_length:
                    self.empty_ports_at_end_of_simulation = False
                    raise ValueError(
                        "The maximum stay of an EV is greater than the simulation length! \n" +
                          "Please increase the simulation length or disable the empty_ports_at_end_of_simulation option")

                if not (self.empty_ports_at_end_of_simulation and
                        self.current_step + 1 + max_stay_of_ev >= self.simulation_length) and \
                        n_ports > cs.n_evs_connected:

                    # get a random float in [0,1] to decide if spawn an EV
                    self.spawn_rate = 0.8
                    if np.random.rand() < self.spawn_rate:
                        ev = EV(id=None,
                                location=cs.id,
                                battery_capacity_at_arrival=np.random.uniform(
                                    1, 49),
                                time_of_arrival=self.current_step+1,
                                earlier_time_of_departure=self.current_step+1
                                + np.random.randint(7, max_stay_of_ev),)
                        # earlier_time_of_departure=self.current_step+1 + np.random.randint(10, 40),)
                        cs.spawn_ev(ev)

                        if self.save_replay:
                            self.EVs.append(ev)

                        self.total_evs_spawned += 1
                        self.current_ev_arrived += 1

        # Spawn EVs
        if self.ev_profiles is not None:
            # Spawn EVs based on the EV profiles onspecific chargers with fixed time of departure, and soc

            counter = self.total_evs_spawned
            for i, ev in enumerate(self.ev_profiles[counter:]):
                print(f"EV {i} at {ev.location} at {ev.time_of_arrival}")
                if ev.time_of_arrival == self.current_step + 1:
                    ev.reset()
                    self.charging_stations[ev.location].spawn_ev(ev)

                    self.total_evs_spawned += 1
                    self.current_ev_arrived += 1
                    if self.save_replay:
                        self.EVs.append(ev)

                elif ev.time_of_arrival > self.current_step + 1:
                    break

        self.current_step += 1
        self._step_date()
        self.current_evs_parked += self.current_ev_arrived - self.current_ev_departed

        # Call step for the grid
        if self.simulate_grid:
            # TODO: transform actions -> grid_actions
            raise NotImplementedError
            grid_report = self.grid.step(actions=actions)
            reward = self._calculate_reward(grid_report)
        else:
            reward = self._calculate_reward(total_costs,
                                            user_satisfaction_list)

        if visualize:
            self.visualize()

        # Check if the episode is done
        if self.current_step >= self.simulation_length or \
                any(score < self.score_threshold for score in user_satisfaction_list) or \
            (any(tr.is_overloaded() for tr in self.transformers)
                    and not self.generate_rnd_game):
            """Terminate if:
                - The simulation length is reached
                - Any user satisfaction score is below the threshold
                - Any charging station is overloaded 
                Dont terminate when overloading if :
                - generate_rnd_game is True
                Carefull: if generate_rnd_game is True, 
                the simulation might end up in infeasible problem
                """

            print(f"\nEpisode finished after {self.current_step} timesteps")

            if self.save_replay:
                self.save_sim_replay()

            self.done = True

            return self._get_observation(), reward, True
        else:
            return self._get_observation(), reward, False

    def save_sim_replay(self):
        '''Saves the simulation data in a pickle file'''
        replay = EvCityReplay(self)
        print(f"Saving replay file at {replay.replay_path}")
        with open(replay.replay_path, 'wb') as f:
            pickle.dump(replay, f)

    def visualize(self):
        '''Renders the current state of the environment in the terminal'''

        print(f"\n Step: {self.current_step}" +
              f" | {self.sim_date.hour}:{self.sim_date.minute}:{self.sim_date.second} |" +
              f" \tEVs +{self.current_ev_arrived}/-{self.current_ev_departed}" +
              f"| fullness: {self.current_evs_parked}/{self.number_of_ports}")

        if self.verbose:
            for cs in self.charging_stations:
                print(f'  - Charging station {cs.id}:')
                print(f'\t Power: {cs.current_power_output:4.1f} kWh |' +
                      f' \u2197 {self.charge_prices[cs.id, self.current_step -1 ]:4.2f} €/kWh ' +
                      f' \u2198 {self.discharge_prices[cs.id, self.current_step - 1]:4.2f} €/kWh |' +
                      f' EVs served: {cs.total_evs_served:3d} ' +
                      f' {cs.total_profits:4.2f} €')

                for port in range(cs.n_ports):
                    ev = cs.evs_connected[port]
                    if ev is not None:
                        print(f'\t\tPort {port}: {ev}')
                    else:
                        print(f'\t\tPort {port}:')
            print("")
            for tr in self.transformers:
                print(tr)

    def print_statistics(self):
        '''Prints the statistics of the simulation'''
        total_ev_served = np.array(
            [cs.total_evs_served for cs in self.charging_stations]).sum()
        total_profits = np.array(
            [cs.total_profits for cs in self.charging_stations]).sum()
        toal_energy_charged = np.array(
            [cs.total_energy_charged for cs in self.charging_stations]).sum()
        total_energy_discharged = np.array(
            [cs.total_energy_discharged for cs in self.charging_stations]).sum()
        average_user_satisfaction = np.average(np.array(
            [cs.get_avg_user_satisfaction() for cs in self.charging_stations]))

        print("\n\n==============================================================")
        print("Simulation statistics:")
        print(f'  - Total EVs spawned: {self.total_evs_spawned}')
        print(f'  - Total EVs served: {total_ev_served}')
        print(f'  - Total profits: {total_profits:.2f} €')
        print(
            f'  - Average user satisfaction: {average_user_satisfaction:.2f} %')

        print(f'  - Total energy charged: {toal_energy_charged:.1f} kWh')
        print(
            f'  - Total energy discharged: {total_energy_discharged:.1f} kWh\n')

        for cs in self.charging_stations:
            print(cs)
        print("==============================================================\n\n")

    def _step_date(self):
        '''Steps the simulation date by one timestep'''
        self.sim_date = self.sim_date + \
            datetime.timedelta(minutes=self.timescale)

    def _get_observation(self, include_grid=False):
        '''Returns the current state of the environment'''
        state = [self.current_step,
                 self.timescale,
                 self.cs,]

        for tr in self.transformers:
            state.append(tr.get_state())

        for cs in self.charging_stations:
            state.append(cs.get_state())

        if include_grid:
            state.append(self.grid.get_grid_state())

        return np.hstack(state)

    def _calculate_reward(self, total_costs, user_satisfaction_list):
        '''Calculates the reward for the current step'''
        reward = total_costs
        return reward
