import numpy as np
import random as rand
import copy
import collections

from multiprocessing import Pool, current_process
from numba import jit, njit
from src.toric_model import Toric_code
from src.planar_model import *
from src.util import *
from src.mcmc import *
from src.mwpm import *

from src.mcmc import MCMCDataReader
from src.mcmc import Chain
import pandas as pd
import time

from math import log, exp
from operator import itemgetter
import random as rand
# Original MCMC Parallel tempering method as descibed in high threshold paper
# Parameters also adapted from that paper.

NUM_POINTS = 500

def PTEQ(init_code, p, Nc=None, SEQ=2, TOPS=10, tops_burn=2, eps=0.1, steps=50000000, iters=10, conv_criteria=None, mwpm_start = False):
    # either 4 or 16 depending on choice of code topology

    if mwpm_start == True:
        mwpm_distr = np.zeros(init_code.nbr_eq_classes)
        mwpm = class_sorted_mwpm(init_code)
        for i in range(len(mwpm_distr)):
            mwpm_distr[i] = -1*mwpm[i].count_errors()
        init_code = mwpm[np.argmax(mwpm_distr)] #fixso that it is real mwpm

    num_points = NUM_POINTS #number of data points in eq steps graph

    nbr_eq_classes = init_code.nbr_eq_classes

    mean_array = np.zeros((nbr_eq_classes, num_points)) # Output array

    # If not specified, use size as per paper
    Nc = Nc or init_code.system_size

    # Warn about incorrect parameter inputs
    if tops_burn >= TOPS:
        print('tops_burn has to be smaller than TOPS')

    # initialize variables
    since_burn = 0
    resulting_burn_in = 0
    nbr_errors_bottom_chain = np.zeros(steps)

    # list of class counts after burn in
    eq = np.zeros([steps, nbr_eq_classes], dtype=np.uint32)

    # used in error_based/majority_based instead of setting tops0 = TOPS
    conv_start = 0
    conv_streak = 0

    # Convergence flag
    convergence_reached = False

    # initialize ladder of chains sampled at different temperatures
    ladder = Ladder(p, init_code, Nc, 0.5)


    # Main loop that runs until convergence or max steps (steps) are reached
    step = 0
    for stages in range(num_points):
        for _ in range(int(steps/num_points)):
            step = step+1
            # run metropolis on every chain and perform chain swaps
            ladder.step(iters)

            # Get sample from eq-class of chain in lowest layer of ladder
            current_eq = ladder.chains[0].code.define_equivalence_class()

            # Start saving stats once burn-in period is over
            if ladder.tops0 >= tops_burn:
                since_burn = step - resulting_burn_in

                eq[since_burn] = eq[since_burn - 1]
                eq[since_burn][current_eq] += 1
                nbr_errors_bottom_chain[since_burn] = ladder.chains[0].code.count_errors()
            else:
                # number of steps until tops0 = 2
                resulting_burn_in += 1

            # Check for convergence every 10 samples if burn-in period is over (and conv-crit is set)
            if conv_criteria == 'error_based' and ladder.tops0 >= TOPS:
                accept, convergence_reached = conv_crit_error_based_PT(nbr_errors_bottom_chain, since_burn, conv_streak, SEQ, eps)
                if accept:
                    if convergence_reached:
                        break
                    conv_streak = ladder.tops0 - conv_start
                else:
                    conv_streak = 0
                    conv_start = ladder.tops0
        if ladder.tops0 >= tops_burn:
            mean_array[:, stages] = (np.divide(eq[since_burn], since_burn + 1) * 100).astype(np.uint8)
        else:
            print(stages)
            mean_array[:, stages] = mwpm_distr #returns mwpm solution
    # print warning if loop is exited without convergence
    else:
        if conv_criteria == 'error_based':
            print('\n\nWARNING: PTEQ hit max number of steps before convergence:\t', step + 1, '\n\n')
    #print(mean_array[:,-1])
    #print(mwpm_distr)
    return np.insert(mean_array, 0, mwpm_distr, axis=1)
    #return mean_array




"""def PTEQ(init_code, p, Nc=None, SEQ=2, TOPS=10, tops_burn=2, eps=0.1, steps=1000000, iters=10, conv_criteria=None, mwpm_start = False):

    # System size is determined from init_code
    size = init_code.system_size

    if mwpm_start == True:
        init_code = class_sorted_mwpm(init_code)[init_code.define_equivalence_class()] #fixso that it is real mwpm



    num_points = NUM_POINTS #number of data points in eq steps graph


    # either 4 or 16 depending on choice of code topology
    nbr_eq_classes = init_code.nbr_eq_classes
    mean_array = np.zeros((nbr_eq_classes, num_points))

    # If not specified, use size as per paper
    Nc = Nc or size

    # Warn about incorrect parameter inputs
    if tops_burn >= TOPS:
        print('tops_burn has to be smaller than TOPS')

    ladder = []  # ladder to store all parallel chains with diffrent temperatures
    p_end = 0.75  # p at top chain is 0.75 (all I,X,Y,Z equally likely)

    # initialize variables
    tops0 = 0
    since_burn = 0
    resulting_burn_in = 0
    nbr_errors_bottom_chain = np.zeros(steps)

    eq = np.zeros([steps, nbr_eq_classes], dtype=np.uint32)  # list of class counts after burn in

    # used in error_based/majority_based instead of setting tops0 = TOPS
    tops_change = 0

    # Convergence flag
    convergence_reached = False

    # Initialize all chains in ladder with same state but different temperatures.
    for i in range(Nc):
        p_i = p + ((p_end - p) / (Nc - 1)) * i # Temperature (in p) for chain i
        ladder.append(Chain( p_i))
        ladder[i].code= copy.deepcopy(init_code)  # give all the same initial state

    # Set probability of application of logical operator in top chain
    ladder[Nc - 1].p_logical = 0.5

    for stages in range(num_points):
        # Main loop that runs until convergence or max steps (steps) are reached
        for j in range(int(steps/num_points)):
            # Run Metropolis steps for each chain in ladder
            for i in range(Nc):
                ladder[i].update_chain(iters)
            # Flag are used to know what chains originating in the top layer of the ladder has found their way down
            # The top chain always generates chains with flag "1". Once such a chain reaches the bottom the flag is
            # reset to 0
            ladder[-1].flag = 1

            # current_eq attempt flips of chains from the top down
            for i in reversed(range(Nc - 1)):
                if r_flip(ladder[i].code.qubit_matrix, ladder[i].p, ladder[i + 1].code.qubit_matrix, ladder[i + 1].p):
                    ladder[i].code, ladder[i + 1].code = ladder[i + 1].code, ladder[i].code
                    ladder[i].flag, ladder[i + 1].flag = ladder[i + 1].flag, ladder[i].flag

            # Update bottom chain flag and add to tops0
            if ladder[0].flag == 1:
                tops0 += 1
                ladder[0].flag = 0

            # Get sample from eq-class of chain in lowest layer of ladder
            current_eq = ladder[0].code.define_equivalence_class()

            # Start saving stats once burn-in period is over
            if tops0 >= tops_burn:
                since_burn = j - resulting_burn_in

                eq[since_burn] = eq[since_burn - 1]
                eq[since_burn][current_eq] += 1
                nbr_errors_bottom_chain[since_burn] = ladder[0].code.count_errors()
            else:
                # number of steps until tops0 = 2
                resulting_burn_in += 1

            # Check for convergence every 10 samples if burn-in period is over (and conv-crit is set)
            if not convergence_reached and tops0 >= TOPS and not since_burn % 10:
                if conv_criteria == 'error_based':
                    tops_accepted = tops0 - tops_change
                    accept, convergence_reached = conv_crit_error_based_PT(nbr_errors_bottom_chain, since_burn, tops_accepted, SEQ, eps)
                    if not accept:
                        tops_change = tops0
            if convergence_reached:
                break

        #print(mean_array)
        mean_array[:, stages] = (np.divide(eq[since_burn], since_burn + 1) * 100).astype(np.uint8)

    return mean_array
"""
@njit(cache=True) # r_flip calculates the quotient called r_flip in paper
def r_flip(qubit_lo, p_lo, qubit_hi, p_hi):
    ne_lo = 0
    ne_hi = 0
    for i in range(2):
        for j in range(qubit_lo.shape[1]):
            for k in range(qubit_lo.shape[1]):
                if qubit_lo[i, j, k] != 0:
                    ne_lo += 1
                if qubit_hi[i, j, k] != 0:
                    ne_hi += 1
    # compute eqn (5) in high threshold paper
    if rand.random() < ((p_lo / p_hi) * ((1 - p_hi) / (1 - p_lo))) ** (ne_hi - ne_lo):
        return True
    return False

# convergence criteria used in paper and called ''felkriteriet''
def conv_crit_error_based_PT(nbr_errors_bottom_chain, since_burn, tops_accepted, SEQ, eps):
    # last nonzero element of nbr_errors_bottom_chain is since_burn. Length of nonzero part is since_burn + 1
    l = since_burn + 1
    # Calculate average number of errors in 2nd and 4th quarter
    Average_Q2 = np.average(nbr_errors_bottom_chain[(l // 4): (l // 2)])
    Average_Q4 = np.average(nbr_errors_bottom_chain[(3 * l // 4): l])

    # Compare averages
    error = abs(Average_Q2 - Average_Q4)
    if error < eps:
        return True, tops_accepted >= SEQ
    else:
        return False, False

#@profile
def single_temp(init_code, p, max_iters, mwpm_start = False):
    nbr_eq_classes = init_code.nbr_eq_classes
    ground_state = init_code.define_equivalence_class()
    ladder = [] # list of chain objects
    nbr_errors_chain = np.zeros((nbr_eq_classes, max_iters))

    num_points = NUM_POINTS
    freq = int(max_iters/num_points)
    mean_array = np.zeros((nbr_eq_classes, num_points-1))
    counter = 0

    """for eq in range(nbr_eq_classes):
        ladder.append(Chain(init_code.system_size, p, copy.deepcopy(init_code)))
        ladder[eq].code.qubit_matrix = ladder[eq].code.to_class(eq) # apply different logical operator to each chain
        ladder[eq].code.qubit_matrix = ladder[eq].code.apply_stabilizers_uniform()"""

    if mwpm_start == True:
         mwpm = class_sorted_mwpm(init_code)

    for eq in range(nbr_eq_classes):
        chain = Chain(init_code.system_size, p, copy.deepcopy(init_code))
        if mwpm_start == False:
            chain.code.qubit_matrix = init_code.to_class(eq)
            chain.code.qubit_matrix = chain.code.apply_stabilizers_uniform()
            ladder.append(chain)
        else:
            chain.code = mwpm[eq]
            ladder.append(chain)


    for eq in range(nbr_eq_classes):
        for j in range(max_iters):
            ladder[eq].update_chain(5)
            nbr_errors_chain[eq ,j] = ladder[eq].code.count_errors()

            if j > 0 and j%freq == 0:
                mean_array[eq][counter] = np.average(nbr_errors_chain[eq ,:j])
                counter+=1
        counter = 0
    return mean_array

#@profile
def STDC(init_code, size, p_error, p_sampling, steps=20000, mwpm_start = False):

    # Create chain with p_sampling, this is allowed since N(n) is independet of p.
    chain = Chain(p_sampling, copy.deepcopy(init_code))

    # this is either 4 or 16, depending on what type of code is used.
    nbr_eq_classes = init_code.nbr_eq_classes

    # this is w we save all samples in a dict, to find the unique ones.
    qubitlist = [{},{},{},{}]


    num_points = NUM_POINTS
    #raindrops = 10 #int(steps/100)

    freq = int(steps/num_points)

    # Z_E will be saved in eqdistr
    eqdistr = np.zeros((nbr_eq_classes, num_points))


    # error-model
    counter = 0
    beta = -log((p_error / 3) / (1 - p_error))
    chain_list = []
    for eq in range(nbr_eq_classes):
        chain = Chain( p_sampling, copy.deepcopy(init_code))
        chain.code.qubit_matrix = init_code.to_class(eq)
        chain.code.qubit_matrix = chain.code.apply_stabilizers_uniform()
        chain_list.append(chain)

    total_counts = 0


    for i in range(num_points):
        for eq in range(nbr_eq_classes):
            # go to class eq and apply stabilizers
            for _ in range(int(steps/num_points)):
                total_counts+=1
                #if int(total_counts/4)%int(steps/raindrops) == 0:
                    #print("STDC", int(total_counts/4))
                #    chain_list[eq].code.qubit_matrix = chain_list[eq].code.apply_stabilizers_uniform()
                chain_list[eq].update_chain(5)
                # add to dict (only gets added if it is new)
                qubitlist[eq][chain_list[eq].code.qubit_matrix.tostring()] = np.count_nonzero(chain_list[eq].code.qubit_matrix)

            # compute Z_E
            #print(eqdistr[eq, counter],'')
            for key in qubitlist[eq]:
                eqdistr[eq, counter] += exp(-beta * qubitlist[eq][key])
        counter+=1

    # Retrun normalized eq_distr
    return eqdistr

def STDC_droplet(input_data_tuple):
    # All unique chains will be saved in samples
    #process = current_process()
    #i = (process._identity[0]-1)%4 # this is because it doesn't reuse process numbers

    #print(i)

    samples = {}
    chain, steps, flag, mwpm_start = input_data_tuple


    # Start in high energy state
    if flag == True and mwpm_start == False:
        chain.code.qubit_matrix = chain.code.apply_stabilizers_uniform()

    # Do the metropolis steps and add to samples if new chains are found
    for _ in range(int(steps)):
        chain.update_chain(5)
        key = chain.code.qubit_matrix.astype(np.uint8).tostring()
        if key not in samples:
            samples[key] = chain.code.count_errors()

    return [samples, chain]

def STDC_rain(init_code, size, p_error, p_sampling=None, droplets=5, steps=20000, mwpm_start = False):
    # set p_sampling equal to p_error by default
    p_sampling = p_sampling or p_error

    # Create chain with p_sampling, this is allowed since N(n) is independet of p.
    chain = Chain( p_sampling, copy.deepcopy(init_code))

    # this is either 4 or 16, depending on what type of code is used.
    nbr_eq_classes = init_code.nbr_eq_classes

    # this is w we save all samples in a dict, to find the unique ones.
    qubitlist = [{},{},{},{}]

    # Z_E will be saved in eqdistr

    num_points = NUM_POINTS
    #raindrops = 10 #int(steps/100)

    freq = int(steps/num_points)

    # Z_E will be saved in eqdistr
    eqdistr = np.zeros((nbr_eq_classes, num_points))
    counter = 0
    beta = -log((p_error / 3) / (1 - p_error))

    chain_list = []

    mwpm = class_sorted_mwpm(init_code)


    for eq in range(nbr_eq_classes):
        drop_list = []
        for _ in range(droplets):
            chain = Chain( p_sampling, copy.deepcopy(init_code))
            if mwpm_start == False:
                chain.code.qubit_matrix = init_code.to_class(eq)
                chain.code.qubit_matrix = chain.code.apply_stabilizers_uniform()
            else:
                chain.code= mwpm[eq]
            drop_list.append(chain)
            #print(chain.code.define_equivalence_class())
        chain_list.append(drop_list)

    #total_counts = 0
    flag = True #decides whether to apply uniform stabilizers in pool
    with Pool(droplets) as pool:
        for i in range(num_points):
            for eq in range(nbr_eq_classes):
                # go to class eq and apply stabilizers
                if droplets == 1:
                    out = STDC_droplet((chain_list[eq][0], int(steps/num_points), flag))
                    output = out[0]
                    chain_output = out[1]
                else:
                    out = pool.map(STDC_droplet, [(chain_list[eq][k], int(steps/num_points), flag, mwpm_start) for k in range(droplets)])
                    output = []
                    chain_output = []
                    for k in range(droplets):
                        output.append(out[k][0])
                        chain_output.append(out[k][1])

                for j in range(droplets):
                    qubitlist[eq].update(output[j])
                    chain_list[eq][j] = chain_output[j]
                # compute Z_E
                for key in qubitlist[eq]:
                    eqdistr[eq, counter] += exp(-beta * qubitlist[eq][key])
            counter+=1
            flag = False

    # Retrun normalized eq_distr
    return eqdistr

#@profile
def STDC_rain_fast(init_code, size, p_error, p_sampling=None, droplets=5, steps=20000, mwpm_start = False):

    # set p_sampling equal to p_error by default
    p_sampling = p_sampling or p_error

    # Create chain with p_sampling, this is allowed since N(n) is independet of p.
    chain = Chain( p_sampling, copy.deepcopy(init_code))

    # this is either 4 or 16, depending on what type of code is used.
    nbr_eq_classes = init_code.nbr_eq_classes

    num_points = NUM_POINTS

    # this is w we save all samples in a dict, to find the unique ones.
    qubitlist = [[{} for _ in range(num_points)] for _ in range(nbr_eq_classes)]

    # Z_E will be saved in eqdistr

    #raindrops = 10 #int(steps/100)

    freq = int(steps/num_points)

    # Z_E will be saved in eqdistr
    eqdistr = np.zeros((nbr_eq_classes, num_points))
    counter = 0
    beta = -log((p_error / 3) / (1 - p_error))

    chain_list = []

    if mwpm_start == True:
         mwpm = class_sorted_mwpm(init_code)
         mwpm_distr = np.zeros((len(mwpm)))

    for eq in range(nbr_eq_classes):
        chain = Chain( p_sampling, copy.deepcopy(init_code))
        if mwpm_start == False:
            chain.code.qubit_matrix = init_code.to_class(eq)
            chain.code.qubit_matrix = chain.code.apply_stabilizers_uniform()
        else:
            chain.code= mwpm[eq]
            mwpm_distr[eq] = -1*mwpm[eq].count_errors() #the shortest chain will give the correct class
        chain_list.append(chain)

    with Pool(droplets*nbr_eq_classes) as pool:
        output = pool.map(STDC_fast_droplet, [(copy.deepcopy(chain_list[eq]), int(steps), mwpm_start, eq, drop, num_points) for drop in range(droplets) for eq in range(nbr_eq_classes)])
    #t0 = time.time()
    for thread in output:
        samples, eq, _ = thread
        for stage in range(num_points):
            qubitlist[eq][stage].update(samples[stage])

    #for thread in output:
    for eq in range(nbr_eq_classes):
        #samples, eq, drop = thread
        for stage in range(num_points):
            for key in qubitlist[eq][stage]:
                eqdistr[eq, stage] += exp(-beta * qubitlist[eq][stage][key])
    tmp = np.insert(eqdistr, 0, mwpm_distr, axis=1) #add the MWPM solution to the start
    #print(mwpm_distr)
    #print(tmp, tmp.shape)
    return tmp

def STDC_fast_droplet(input_data_tuple):
    chain, steps, mwpm_start, eq, drop, num_points = input_data_tuple
    samples = [{} for _ in range(num_points)]
    # Start in high energy state
    if mwpm_start == False:
        chain.code.qubit_matrix = chain.code.apply_stabilizers_uniform()
    # Do the metropolis steps and add to samples if new chains are found
    for stage in range(num_points):
        for step in range(int(steps/num_points)):
            chain.update_chain(5)
            key = chain.code.qubit_matrix.astype(np.uint8).tostring()
            if key not in samples[stage]:
                for sample in samples[stage:]:
                    sample[hash(key)] = chain.code.count_errors()
    return (samples, eq, drop)

def STRC_rain(init_code, size, p_error, p_sampling=None, droplets=5, steps=20000):
    # set p_sampling equal to p_error by default
    p_sampling = p_sampling or p_error

    # Either 4 or 16, depending on type of code
    nbr_eq_classes = init_code.nbr_eq_classes

    #number of data points for plot
    num_points = NUM_POINTS

    # Create chain with p_sampling, this is allowed since N(n) is independet of p.
    #chain = Chain( p_sampling, copy.deepcopy(init_code))

    chain_list = []

    for eq in range(nbr_eq_classes):
        chain = Chain( p_sampling, copy.deepcopy(init_code))
        chain.code.qubit_matrix = init_code.to_class(eq)
        chain.code.qubit_matrix = chain.code.apply_stabilizers_uniform()
        chain_list.append(chain)

    unique_lengths = [{},{},{},{}]
    len_counts = [{},{},{},{}]

    counts  = 0
    total_counts = 0

    # error model
    beta_error = -log((p_error / 3) / (1 - p_error))
    beta_sampling = -log((p_sampling / 3) / (1 - p_sampling))
    d_beta = beta_sampling - beta_error

    # Array to hold the boltzmann factors for every class
    Z_arr = np.zeros((nbr_eq_classes, num_points))

    # Largest possible chain length
    max_length = 2 * size ** 2

    short_stats_list = [[{} for _ in range(2)],
                        [{} for _ in range(2)],
                        [{} for _ in range(2)],
                        [{} for _ in range(2)]]


    flag = True # Determines if apply uniform stabilizers

    shortest = np.ones((nbr_eq_classes)) * max_length
    next_shortest = np.ones((nbr_eq_classes)) * max_length
    # Iterate through equivalence classes
    with Pool(droplets) as pool:
        for stages in range(num_points):
            for eq in range(nbr_eq_classes):
                short_unique = short_stats_list[eq]
                # Start parallel processes with droplets.
                if droplets == 1:
                    unique_lengths_i, len_counts_i, short_unique_i, _,_ = STRC_droplet((chain_list[eq], int(steps/num_points), max_length, copy.deepcopy(short_unique), copy.deepcopy(len_counts[eq]), copy.deepcopy(unique_lengths[eq]), eq, flag))
                else:
                    output = pool.map(STRC_droplet, [(copy.deepcopy(chain_list[eq]), int(steps/num_points), max_length, eq, flag) for _ in range(droplets)])
                flag = False

                #print(eq, short_unique[0].values())
                # Find shortest and next shortest length found by any chain
                for i in range(droplets):
                    if droplets > 1:
                        _,_,data, _, _ = output[i]
                    elif droplets == 1:
                        data = short_unique_i
                    if list(data[0].values())[0] < shortest[eq]:
                        next_shortest[eq] = shortest[eq]
                        shortest[eq] = list(data[0].values())[0]
                    if list(data[1].values())[0] < next_shortest[eq]:
                        next_shortest[eq] = list(data[1].values())[0]

                # Add data from each droplet to the combined dataset
                for i in range(droplets):
                    # Unpack results
                    if droplets > 1: unique_lengths_i, len_counts_i, short_unique_i,_,_ = output[i]

                    # Combine unique lengths ( not really needed? )
                    unique_lengths[eq].update(unique_lengths_i)

                    # Combine len_counts
                    for key in len_counts_i:
                        if key in len_counts[eq]:
                            len_counts[eq][key] += len_counts_i[key]
                        else:
                            len_counts[eq][key] = len_counts_i[key]

                    # Combine the sets of shortest and next shortest chains
                    shortest_i = list(short_unique_i[0].values())[0]
                    next_shortest_i = list(short_unique_i[1].values())[0]

                    if shortest_i == shortest[eq]:
                        short_unique[0].update(short_unique_i[0])
                    if shortest_i == next_shortest[eq]:
                        short_unique[1].update(short_unique_i[0])
                    if next_shortest_i == next_shortest[eq]:
                        short_unique[1].update(short_unique_i[1])

                    if shortest_i < shortest[eq]:
                        next_shortest[eq] = shortest[eq]
                        shortest[eq] = shortest_i
                        short_unique[1].clear()
                        short_unique[1].update(short_unique[0])
                        short_unique[0].clear()
                        short_unique[0].update(short_unique_i[0])

                    elif shortest_i < next_shortest[eq]:
                        next_shortest[eq] = shortest_i
                        short_unique[1].clear()
                        short_unique[1].update(short_unique_i[1])

                    if next_shortest_i < next_shortest[eq]:
                        next_shortest[eq] = next_shortest_i
                        short_unique[1].clear()
                        short_unique[1].update(short_unique_i[1])

                # Partial result needed for boltzmann factor
                shortest_count = len(short_unique[0])
                shortest_fraction = shortest_count / len_counts[eq][shortest[eq]]

                next_shortest_count = len(short_unique[1])

                # Handle rare cases w only one chain length is observed
                if next_shortest[eq] != max_length:
                    next_shortest_fraction = next_shortest_count / len_counts[eq][next_shortest[eq]]
                    mean_fraction = 0.5 * (shortest_fraction + next_shortest_fraction * exp(-beta_sampling * (next_shortest[eq] - shortest[eq])))

                else:
                    mean_fraction = shortest_fraction

                # Calculate boltzmann factor from observed chain lengths
                Z_e = sum([m * exp(-beta_sampling * shortest[eq] + d_beta * l) for l, m in len_counts[eq].items()]) * mean_fraction
                Z_arr[eq, counts] = Z_e
            counts+=1
    return Z_arr

def STRC_droplet(input_data_tuple):
    chain, steps, max_length, eq, flag = input_data_tuple
    unique_lengths = {}
    len_counts = {}
    short_unique = [{} for _ in range(2)] #short_unique
    #len_counts = len_counts
    #unique_lengths = unique_lengths

    # List of unique shortest and next shortets chains
    short_unique[0]['temp'] = max_length
    short_unique[1]['temp'] = max_length

    # Variables to easily keep track of the length of chains in short_unique
    shortest = max_length
    next_shortest = max_length
    # Apply random stabilizers to start in high temperature state
    if flag == True:

        chain.code.qubit_matrix = chain.code.apply_stabilizers_uniform()

    # Apply logical operators to get qubit_matrix into equivalence class eq
    #chain.code.qubit_matrix = chain.code.to_class(eq)

    # Generate chains
    for step in range(steps):
        # Do metropolis sampling
        chain.update_chain(5)

        # Convert the current qubit matrix to string for hashing
        key = chain.code.qubit_matrix.tostring()

        # Check if this error chain has already been seen by comparing hashes
        if key in unique_lengths:
            # Increment counter for chains of this length
            len_counts[unique_lengths[key]] += 1

        # If this chain is new, add it to dictionary of unique chains
        else:
            # Calculate length of this chain
            length = chain.code.count_errors()
            # Store number of observations and length of this chain
            unique_lengths[key] = length
            # Check if this length has been seen before
            if length in len_counts:
                len_counts[unique_lengths[key]] += 1

                # Check if this chain is same length as previous shortest chain
                if length == shortest:
                    # Then add it to the set of seen short chains
                    short_unique[0][key] = length

                # Otherwise, check if this chain same length as previous next shortest chain
                elif length == next_shortest:
                    # Then add it to the set of seen next shortest chains
                    short_unique[1][key] = length

            else:
                # Initiate counter for chains of this length
                len_counts[unique_lengths[key]] = 1
                # Check if this chain is shorter than prevous shortest chain
                if length < shortest:
                    # Then the previous shortest length is the new next shortest
                    next_shortest = shortest
                    shortest = length

                    # Clear next shortest set and set i equal to shortest
                    short_unique[1].clear()
                    short_unique[1].update(short_unique[0])
                    # And the current length is the new shortest
                    short_unique[0].clear()

                    short_unique[0][key] = length

                # Otherwise, check if this chain is shorter than previous next shortest chain
                elif length < next_shortest:
                    # Then reset stats of next shortest chain
                    next_shortest = length

                    # Clear and update next shortest set
                    short_unique[1].clear()
                    short_unique[1][key] = length

    return  unique_lengths, len_counts, short_unique, next_shortest,  shortest #unique_lengths, len_counts, short_unique

def STRC(init_code, size, p_error, p_sampling=None, steps=20000, mwpm_start = False):
    nbr_eq_classes = init_code.nbr_eq_classes
    num_points = NUM_POINTS
    #raindrops = 10 #int(steps/100)

    p_sampling = p_sampling or p_error
    beta_error = -log((p_error / 3) / (1 - p_error))
    beta_sampling = -log((p_sampling / 3) / (1 - p_sampling))
    d_beta = beta_sampling - beta_error

    Z_arr = np.zeros((nbr_eq_classes, num_points))
    max_length = 2 * size ** 2


    #chain = Chain( p_sampling, copy.deepcopy(init_code))  # this p needs not be the same as p, as it is used to determine how we sample N(n)

    chain_list = []

    if mwpm_start == True:
         mwpm = class_sorted_mwpm(init_code)

    for eq in range(nbr_eq_classes):
        chain = Chain( p_sampling, copy.deepcopy(init_code))
        if mwpm_start == False:
            chain.code.qubit_matrix = init_code.to_class(eq)
            chain.code.qubit_matrix = chain.code.apply_stabilizers_uniform()
            chain_list.append(chain)
        else:
            chain.code = mwpm[eq]
            chain_list.append(chain)


    unique_lengths = [{},{},{},{}]
    len_counts = [{},{},{},{}]
    short_stats_list = [[{'n':max_length, 'N':0} for _ in range(2)],
                        [{'n':max_length, 'N':0} for _ in range(2)],
                        [{'n':max_length, 'N':0} for _ in range(2)],
                        [{'n':max_length, 'N':0} for _ in range(2)]]
    counts  = 0
    total_counts = 0

    for i in range(num_points):
        for eq in range(nbr_eq_classes):
            #unique_lengths = {}
            #len_counts = {}
            # List w first (last) element is stats of shortest (next shortest) length
            # n is length of chain. N is number of unique chains of this length
            short_stats = short_stats_list[eq]
            #chain.code = init_code
            # Apply logical operators to get qubit_matrix into equivalence class i
            #chain.code.qubit_matrix = chain.code.to_class(eq)

            for step in range(int(steps/num_points)):
                total_counts+=1
                #if int(total_counts/4)%int(steps/raindrops) == 0:
                    #print("STRC", int(total_counts/4))
                #    chain_list[eq].code.qubit_matrix = chain_list[eq].code.apply_stabilizers_uniform()

                chain_list[eq].update_chain(5)
                key = chain_list[eq].code.qubit_matrix.tostring()

                # Check if this error chain has already been seen
                if key in unique_lengths[eq]:
                    # Increment counter for chains of this length
                    len_counts[eq][unique_lengths[eq][key]] += 1

                # If this chain is new, add it to dictionary of unique chains
                else:
                    # Calculate length of this chain
                    length = chain_list[eq].code.count_errors()
                    # Store number of observations and length of this chain
                    unique_lengths[eq][key] = length

                    # Check if this length has been seen before
                    if length in len_counts[eq]:
                        len_counts[eq][unique_lengths[eq][key]] += 1

                        # Otherwise, check if this chain is same length as previous shortest chain
                        if length == short_stats[0]['n']:
                            # Then increment counter of unique chains of shortest length
                            short_stats[0]['N'] += 1

                        # Otherwise, check if this chain same length as previous next shortest chain
                        elif length == short_stats[1]['n']:
                            # Then increment counter of unique chains of next shortest length
                            short_stats[1]['N'] += 1

                    else:
                        # Initiate counter for chains of this length
                        len_counts[eq][unique_lengths[eq][key]] = 1
                        # Check if this chain is shorter than prevous shortest chain
                        if length < short_stats[0]['n']:
                            # Then the previous shortest length is the new next shortest
                            short_stats[1] = short_stats[0]
                            # And the current length is the new shortest
                            short_stats[0] = {'n':length, 'N':1}

                        # Otherwise, check if this chain is shorter than previous next shortest chain
                        elif length < short_stats[1]['n']:
                            # Then reset stats of next shortest chain
                            short_stats[1] = {'n':length, 'N':1}

            # Calculate Boltzmann factor for eq from observed chain lengths
            shortest = short_stats[0]['n']
            shortest_count = short_stats[0]['N']
            shortest_fraction = shortest_count / len_counts[eq][shortest]
            yn = (shortest_count-1) / len_counts[eq][shortest]
            if shortest_fraction != 1:
                """for i in range(100):
                    #print(len_counts[eq][shortest]*yn**(len_counts[eq][shortest]-1)-shortest_count, "")
                    yn = ((len_counts[eq][shortest]-1)*yn**len_counts[eq][shortest]-(shortest_count-1))/(len_counts[eq][shortest]*yn**(len_counts[eq][shortest]-1)-shortest_count)
                shortest_fraction = (1/(1-yn)-1)/shortest_count"""
                m = len_counts[eq][shortest]
                k = shortest_count
                #shortest_fraction = m*(m-1)/2/(m-k)/m





            next_shortest = short_stats[1]['n']
            next_shortest_count = short_stats[1]['N']

            if next_shortest != max_length:
                next_shortest_fraction = next_shortest_count / len_counts[eq][next_shortest]
                #print(next_shortest_fraction, "next_shortest_fraction")
                if next_shortest_fraction !=1:
                    m = len_counts[eq][next_shortest]
                    k = next_shortest_count
                    """yn = (next_shortest_count-1)/next_shortest_count
                    for i in range(1000):
                        #print(len_counts[eq][next_shortest]*yn**(len_counts[eq][next_shortest]-1)-next_shortest_count, len_counts[eq][next_shortest]*yn**(len_counts[eq][next_shortest]-1),"2")
                        yn = ((len_counts[eq][next_shortest]-1)*yn**len_counts[eq][next_shortest]-(next_shortest_count-1))/(len_counts[eq][next_shortest]*yn**(len_counts[eq][next_shortest]-1)-next_shortest_count)
                    print("line 697", (1/(1-yn)-1), next_shortest_count)
                    next_shortest_fraction = (1/(1-yn)-1)/next_shortest_count"""
                    #next_shortest_fraction = m*(m-1)/2/(m-k)/m
                    #print("line 702", m*(m-1)/2/(m-k) , next_shortest_count)

                    #print(yn, next_shortest_count)


                mean_fraction = 0.5 * (shortest_fraction + next_shortest_fraction * exp(-beta_sampling * (next_shortest - shortest)))

            else:
                mean_fraction = shortest_fraction

            Z_e = sum([m * exp(-beta_sampling * shortest + d_beta * l) for l, m in len_counts[eq].items()]) * mean_fraction

            Z_arr[eq, counts] = Z_e

            short_stats_list[eq] = short_stats
        counts+=1
    return Z_arr


if __name__ == '__main__':
    init_code = Planar_code(5)
    p=0.20
    init_code.generate_random_error(p)

    x = STDC_rain_fast(init_code, size=3, p_error=p, p_sampling=None, droplets=4, steps=20000, mwpm_start = True)
    print(x)
