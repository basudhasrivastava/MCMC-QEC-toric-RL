import numpy as np
import matplotlib.pyplot as plt
from random import uniform, randint, random
from numba import jit, njit
import random as rand

class Planar_code():
    nbr_eq_classes = 4
    
    def __init__(self, size):
        self.system_size = size
        self.qubit_matrix = np.zeros((2, self.system_size, self.system_size), dtype=np.uint8)
        self.plaquette_matrix = np.zeros((size, size-1), dtype=int)
        self.vertex_matrix = np.zeros((size-1, size), dtype=int)
        self.syndrom = np.copy(self.qubit_matrix)


    def generate_random_error(self, p_error):
        #for i in range(2):
        qubits = np.random.uniform(0, 1, size=(2, self.system_size, self.system_size))
        no_error = qubits > p_error
        error = qubits < p_error
        qubits[no_error] = 0
        qubits[error] = 1
        pauli_error = np.random.randint(3, size=(2, self.system_size, self.system_size)) + 1
        self.qubit_matrix[:,:,:] = np.multiply(qubits, pauli_error)
        self.qubit_matrix[1,-1,:] = 0
        self.qubit_matrix[1,:,-1] = 0
        #self.syndrom()


    def count_errors(self):
        return _count_errors(self.qubit_matrix)


    def apply_logical(self, operator=int, X_pos=0, Z_pos=0):
        return _apply_logical(self.qubit_matrix, operator, X_pos, Z_pos)


    def apply_stabilizer(self, row=int, col=int, operator=int):
        return _apply_stabilizer(self.qubit_matrix, row, col, operator)


    def apply_random_logical(self):
        return _apply_random_logical(self.qubit_matrix)


    def apply_random_stabilizer(self):
        return _apply_random_stabilizer(self.qubit_matrix)


    def apply_stabilizers_uniform(self, p=0.5):
        return _apply_stabilizers_uniform(self.qubit_matrix, p)


    def define_equivalence_class(self):
        # of x errors in the first coulum
        x_errors = np.count_nonzero(self.qubit_matrix[0,:,0]==1)
        x_errors += np.count_nonzero(self.qubit_matrix[0,:,0]==2)

        # of z errors in the first row
        z_errors = np.count_nonzero(self.qubit_matrix[0,0,:]==3)
        z_errors += np.count_nonzero(self.qubit_matrix[0,0,:]==2)

        # return the parity of the calculated #'s of errors
        return (x_errors % 2) + 2 * (z_errors % 2)


    def to_class(self, eq=int): # apply_logical_operators i decoders.py
        diff = eq ^ self.define_equivalence_class()
        mask = 0b10
        xor = (mask & diff) >> 1
        op = diff ^ xor

        qubit_matrix, _ = self.apply_logical(operator=op, X_pos=0, Z_pos=0)

        return qubit_matrix


    def syndrom(self):
        # generate vertex excitations (charge)
        # can be generated by z and y errors 
        qubit0 = self.qubit_matrix[0,:,:]        
        charge = (qubit0 == 2 or qubit0 == 3).astype(int) # separate y and z errors from x 
        charge_shift = np.zeros_like(charge)
        charge_shift[1:] = charge[:-1]
        charge = charge + charge_shift
        charge0 = (charge == 1).astype(int) # annihilate two syndroms at the same place in the grid
        
        qubit1 = self.qubit_matrix[1,:self.size-1,:self.size-1]        
        y_errors = (qubit1 == 2).astype(int)
        z_errors = (qubit1 == 3).astype(int)
        charge = y_errors + z_errors
        charge_shift = np.roll(charge, 1, axis=1)
        charge1 = charge + charge_shift
        charge1 = (charge1 == 1).astype(int)
        
        charge = charge0 + charge1
        vertex_matrix = (charge == 1).astype(int)
        
        # generate plaquette excitation (flux)
        # can be generated by x and y errors
        qubit0 = self.qubit_matrix[0,:,:]        
        x_errors = (qubit0 == 1).astype(int)
        y_errors = (qubit0 == 2).astype(int)
        flux = x_errors + y_errors # plaquette_excitation
        flux_shift = np.roll(flux, -1, axis=1)
        flux = flux + flux_shift
        flux0 = (flux == 1).astype(int)
        
        qubit1 = self.qubit_matrix[1,:,:]        
        x_errors = (qubit1 == 1).astype(int)
        y_errors = (qubit1 == 2).astype(int)
        flux = x_errors + y_errors
        flux_shift = np.roll(flux, -1, axis=0)
        flux1 = flux + flux_shift
        flux1 = (flux1 == 1).astype(int)

        flux = flux0 + flux1
        plaquette_matrix = (flux == 1).astype(int)

        self.syndrom = np.stack((vertex_matrix, plaquette_matrix), axis=0)


    def syndrom_old(self):
        # generate vertex excitations (charge)
        # can be generated by z and y errors 
        qubit0 = self.qubit_matrix[0,:,:]        
        y_errors = (qubit0 == 2).astype(int) # separate y and z errors from x 
        z_errors = (qubit0 == 3).astype(int)
        charge = y_errors + z_errors # vertex_excitation
        charge_shift = np.roll(charge, 1, axis=0)
        charge = charge + charge_shift
        charge0 = (charge == 1).astype(int) # annihilate two syndroms at the same place in the grid

        qubit1 = self.qubit_matrix[1,:,:]
        y_errors = (qubit1 == 2).astype(int)
        z_errors = (qubit1 == 3).astype(int)
        charge = y_errors + z_errors
        charge_shift = np.roll(charge, 1, axis=1)
        charge1 = charge + charge_shift
        charge1 = (charge1 == 1).astype(int)

        charge = charge0 + charge1
        vertex_matrix = (charge == 1).astype(int)

        # generate plaquette excitation (flux)
        # can be generated by x and y errors
        qubit0 = self.qubit_matrix[0,:,:]
        x_errors = (qubit0 == 1).astype(int)
        y_errors = (qubit0 == 2).astype(int)
        flux = x_errors + y_errors # plaquette_excitation
        flux_shift = np.roll(flux, -1, axis=1)
        flux = flux + flux_shift
        flux0 = (flux == 1).astype(int)

        qubit1 = self.qubit_matrix[1,:,:]
        x_errors = (qubit1 == 1).astype(int)
        y_errors = (qubit1 == 2).astype(int)
        flux = x_errors + y_errors
        flux_shift = np.roll(flux, -1, axis=0)
        flux1 = flux + flux_shift
        flux1 = (flux1 == 1).astype(int)

        flux = flux0 + flux1
        plaquette_matrix = (flux == 1).astype(int)

        self.syndrom = np.stack((vertex_matrix, plaquette_matrix), axis=0)


    def plot_toric_code(self, title, eq_class=None):
        x_error_qubits1 = np.where(self.qubit_matrix[0,:,:] == 1)
        y_error_qubits1 = np.where(self.qubit_matrix[0,:,:] == 2)
        z_error_qubits1 = np.where(self.qubit_matrix[0,:,:] == 3)

        x_error_qubits2 = np.where(self.qubit_matrix[1,:,:] == 1)
        y_error_qubits2 = np.where(self.qubit_matrix[1,:,:] == 2)
        z_error_qubits2 = np.where(self.qubit_matrix[1,:,:] == 3)

        vertex_matrix = self.syndrom[0,:,:]
        plaquette_matrix = self.syndrom[1,:,:]
        vertex_defect_coordinates = np.where(vertex_matrix)
        plaquette_defect_coordinates = np.where(plaquette_matrix)

        #xLine = np.linspace(0, self.system_size-0.5, self.system_size)
        xLine = np.linspace(0, self.system_size, self.system_size)
        x = range(self.system_size)
        X, Y = np.meshgrid(x,x)
        XLine, YLine = np.meshgrid(x, xLine)

        markersize_qubit = 15
        markersize_excitation = 7
        markersize_symbols = 7
        linewidth = 2

        ax = plt.subplot(111)
        ax.plot(XLine, -YLine, 'black', linewidth=linewidth)
        ax.plot(YLine, -XLine, 'black', linewidth=linewidth)

        # add the last two black lines
        ax.plot(XLine[:,-1] + 1.0, -YLine[:,-1], 'black', linewidth=linewidth)
        ax.plot(YLine[:,-1], -YLine[-1,:], 'black', linewidth=linewidth)

        ax.plot(X + 0.5, -Y, 'o', color = 'black', markerfacecolor = 'white', markersize=markersize_qubit+1)
        ax.plot(X, -Y -0.5, 'o', color = 'black', markerfacecolor = 'white', markersize=markersize_qubit+1)
        # add grey qubits
        ax.plot(X[-1,:] + 0.5, -Y[-1,:] - 1.0, 'o', color = 'black', markerfacecolor = 'grey', markersize=markersize_qubit+1)
        ax.plot(X[:,-1] + 1.0, -Y[:,-1] - 0.5, 'o', color = 'black', markerfacecolor = 'grey', markersize=markersize_qubit+1)

        # all x errors
        ax.plot(x_error_qubits1[1], -x_error_qubits1[0] - 0.5, 'o', color = 'r', label="x error", markersize=markersize_qubit)
        ax.plot(x_error_qubits2[1] + 0.5, -x_error_qubits2[0], 'o', color = 'r', markersize=markersize_qubit)
        ax.plot(x_error_qubits1[1], -x_error_qubits1[0] - 0.5, 'o', color = 'black', markersize=markersize_symbols, marker=r'$X$')
        ax.plot(x_error_qubits2[1] + 0.5, -x_error_qubits2[0], 'o', color = 'black', markersize=markersize_symbols, marker=r'$X$')

        # all y errors
        ax.plot(y_error_qubits1[1], -y_error_qubits1[0] - 0.5, 'o', color = 'blueviolet', label="y error", markersize=markersize_qubit)
        ax.plot(y_error_qubits2[1] + 0.5, -y_error_qubits2[0], 'o', color = 'blueviolet', markersize=markersize_qubit)
        ax.plot(y_error_qubits1[1], -y_error_qubits1[0] - 0.5, 'o', color = 'black', markersize=markersize_symbols, marker=r'$Y$')
        ax.plot(y_error_qubits2[1] + 0.5, -y_error_qubits2[0], 'o', color = 'black', markersize=markersize_symbols, marker=r'$Y$')

        # all z errors
        ax.plot(z_error_qubits1[1], -z_error_qubits1[0] - 0.5, 'o', color = 'b', label="z error", markersize=markersize_qubit)
        ax.plot(z_error_qubits2[1] + 0.5, -z_error_qubits2[0], 'o', color = 'b', markersize=markersize_qubit)
        ax.plot(z_error_qubits1[1], -z_error_qubits1[0] - 0.5, 'o', color = 'black', markersize=markersize_symbols, marker=r'$Z$')
        ax.plot(z_error_qubits2[1] + 0.5, -z_error_qubits2[0], 'o', color = 'black', markersize=markersize_symbols  , marker=r'$Z$')


        #ax.plot(vertex_defect_coordinates[1], -vertex_defect_coordinates[0], 'x', color = 'blue', label="charge", markersize=markersize_excitation)
        ax.plot(vertex_defect_coordinates[1], -vertex_defect_coordinates[0], 'o', color = 'blue', label="charge", markersize=markersize_excitation)
        ax.plot(plaquette_defect_coordinates[1] + 0.5, -plaquette_defect_coordinates[0] - 0.5, 'o', color = 'red', label="flux", markersize=markersize_excitation)
        ax.axis('off')

        if eq_class:
            ax.set_title('Equivalence class: ' +  str(eq_class))

        #plt.title(title)
        plt.axis('equal')
        plt.savefig('plots/graph_'+str(title)+'.png')
        plt.close()


@njit
def _apply_logical(qubit_matrix, operator=int, X_pos=0, Z_pos=0):
    # Have to make copy, else original matrix is changed
    result_qubit_matrix = np.copy(qubit_matrix)

    # Operator is zero means identity, no need to keep going
    if operator == 0:
        return result_qubit_matrix, 0
    size = qubit_matrix.shape[1]
    layer = 0

    error_count = 0

    do_X = (operator == 1 or operator == 2)
    do_Z = (operator == 3 or operator == 2)

    # Helper function
    def qubit_update(row, col, op):
        old_qubit = result_qubit_matrix[layer, row, col]
        new_qubit = old_qubit ^ op
        result_qubit_matrix[layer, row, col] = new_qubit
        if old_qubit and not new_qubit:
            return -1
        elif new_qubit and not old_qubit:
            return 1
        else:
            return 0

    for i in range(size):
        if do_X:
            error_count += qubit_update(X_pos, i, 1)
        if do_Z:
            error_count += qubit_update(i, Z_pos, 3)
    
    return result_qubit_matrix, error_count


@njit
def _apply_random_logical(qubit_matrix):
    size = qubit_matrix.shape[1]

    # operator to use, 2 (Y) will make both X and Z on the same layer. 0 is identity
    # one operator for each layer
    op = int(random() * 4)

    if op == 1 or op == 2:
        X_pos = int(random() * size)
    else:
        X_pos = 0
    if op == 3 or op == 2:
        Z_pos = int(random() * size)
    else:
        Z_pos = 0

    return _apply_logical(qubit_matrix, op, X_pos, Z_pos)


@njit
def _apply_random_stabilizer(qubit_matrix):
    size = qubit_matrix.shape[1]
    if rand.random() < 0.5:
        # operator = 1 = x
        return _apply_stabilizer(qubit_matrix,rand.randint(0,size-2),rand.randint(0,size-1),1)
    else: 
        # operator = 3 = z
        return _apply_stabilizer(qubit_matrix,rand.randint(0,size-1),rand.randint(0,size-2),3)


@njit
def _apply_stabilizer(qubit_matrix, row=int, col=int, operator=int):
    # gives the resulting qubit error matrix from applying (row, col, operator) stabilizer
    # doesn't update input qubit_matrix
    size = qubit_matrix.shape[1]
    if operator == 1:
        # Special cases depending on where the stabilizer lives (square/triangle - in the middle/on the boundary)
        if col == 0:
            qubit_matrix_layers = np.array([0, 0, 1])
            rows = np.array([row, row + 1, row])
            cols = np.array([0, 0, 0])
        elif col == size - 1:
            qubit_matrix_layers = np.array([0, 0, 1])
            rows = np.array([row, row + 1, row])
            cols = np.array([col, col, col - 1])
        else:
            qubit_matrix_layers = np.array([0, 0, 1, 1])
            rows = np.array([row, row + 1, row, row])
            cols = np.array([col, col, col, col - 1])

    elif operator == 3:
        # Special cases depending on where the stabilizer lives (square/triangle - in the middle/on the boundary)
        if row == 0:
            qubit_matrix_layers = np.array([0, 0, 1])
            rows = np.array([0, 0, 0])
            cols = np.array([col, col + 1, col])
        elif row == size - 1:
            qubit_matrix_layers = np.array([0, 0, 1])
            rows = np.array([row, row, row - 1])
            cols = np.array([col, col + 1, col])
        else:
            qubit_matrix_layers = np.array([0, 0, 1, 1])
            rows = np.array([row, row, row, row - 1])
            cols = np.array([col, col + 1, col, col]) 

    # Have to make copy, else original matrix is changed
    result_qubit_matrix = np.copy(qubit_matrix)
    error_count = 0
    for i in range(len(qubit_matrix_layers)):
        old_qubit = qubit_matrix[qubit_matrix_layers[i], rows[i], cols[i]]
        new_qubit = operator ^ old_qubit
        result_qubit_matrix[qubit_matrix_layers[i], rows[i], cols[i]] = new_qubit
        if old_qubit and not new_qubit:
            error_count -= 1
        elif new_qubit and not old_qubit:
            error_count += 1

    return result_qubit_matrix, error_count

def _apply_stabilizers_uniform(qubit_matrix, p=0.5):
    size = qubit_matrix.shape[1]
    result_qubit_matrix = np.copy(qubit_matrix)
    random_stabilizers = np.random.rand(2, size, size)
    random_stabilizers = np.less(random_stabilizers, p)

    # Remove stabilizers from illegal positions
    #x-operators at bottom
    random_stabilizers[1,size-1,:] = 0
    #z-operators at right edge
    random_stabilizers[0,:,size-1] = 0

    # Numpy magic for iterating through matrix
    it = np.nditer(random_stabilizers, flags=['multi_index'])
    while not it.finished:
        if it[0]:
            op, row, col = it.multi_index
            if op == 0:
                op = 3
            result_qubit_matrix, _ = _apply_stabilizer(result_qubit_matrix, row, col, op)
        it.iternext()
    return result_qubit_matrix


@jit(nopython=True)
def _count_errors(qubit_matrix): # Kolla så inte fel
    return np.count_nonzero(qubit_matrix)
