"""
This script reads the results of the baselines and creates a table comparing the different metrics.
"""

import numpy as np
import pickle

algorithms = ['ddpg', 'td3', 'sac', 'a2c', 'ppo', 'tqc', 'trpo', 'ars', 'rppo']
# algorithms = ['td3','ddpg', 'sac']

results_table = np.zeros((len(algorithms), 14))

for index, algorithm in enumerate(algorithms):
    try:
        # with open("./results/" + algorithm + "_20cs_1_port.pkl", "rb") as f:
        with open("./results/" + algorithm + "_50cs_1_port_SqTrError_TrPenalty_UserIncentives.pkl", "rb") as f:
            results = pickle.load(f)
    except FileNotFoundError:
        print("No results for ", algorithm)
        continue

    print(algorithm, len(results))
    results_table[index, 0] = np.array(
        [i[0]['total_ev_served'] for i in results]).mean()
    results_table[index, 1] = np.array(
        [i[0]['total_ev_served'] for i in results]).std()

    results_table[index, 2] = np.array(
        [i[0]['total_energy_charged'] for i in results]).mean()
    results_table[index, 3] = np.array(
        [i[0]['total_energy_charged'] for i in results]).std()

    results_table[index, 4] = np.array(
        [i[0]['tracking_error'] for i in results]).mean()
    results_table[index, 5] = np.array(
        [i[0]['tracking_error'] for i in results]).std()

    results_table[index, 6] = np.array(
        [i[0]['power_tracker_violation'] for i in results]).mean()
    results_table[index, 7] = np.array(
        [i[0]['power_tracker_violation'] for i in results]).std()

    results_table[index, 8] = np.array(
        [i[0]['episode']['r'] for i in results]).mean()
    results_table[index, 9] = np.array(
        [i[0]['episode']['r'] for i in results]).std()
    
    results_table[index, 10] = np.array(
        [i[0]['total_transformer_overload'] for i in results]).mean()
    results_table[index, 11] = np.array(
        [i[0]['total_transformer_overload'] for i in results]).std()
    
    results_table[index, 12] = np.array(
        [i[0]['average_user_satisfaction'] for i in results]).mean()
    results_table[index, 13] = np.array(
        [i[0]['average_user_satisfaction'] for i in results]).std()


# print results in a table format using | as separator and 2 decimal precision


column_keys = ['algorithm', 'EVs served', 'Energy charged',
               'Tracking error', 'Power Surplass', 'Reward',
               'Tr. Overload', 'User Sat.%']


for key in column_keys:
    # center string and print

    print(f'{key:^16s}', end=" | ")
print()
print("-"*len(column_keys)*18)
for index, algorithm in enumerate(algorithms):
    print(f'{algorithm:^15s}', end=" | ")

    for i in range(5):
        print(
            f"{results_table[index,2*i]:7.1f} +/-{results_table[index,2*i+1]:<6.1f}|", end=" ")

    print("")
    print("-"*len(column_keys)*18)
