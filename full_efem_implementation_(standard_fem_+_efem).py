# -*- coding: utf-8 -*-
"""Full EFEM Implementation (Standard FEM + EFEM).ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1Gyc36kAJOQ5m0jXe_taP0cEML3wjBfSX

THIS FIRST CODE IS A SIMPLE FE IMPLEMENTATION FOR A CST ELEMENT. IT IS THE BASIS AND WILL BE IMPROVED AFTERWARDS.

THIS IS THE ENHANCED VERSION OF THE METHOD. IT INVOLVES INCREMENTAL STEPS AND SLOWLY ARRIVES AT THE FINAL VERSION.

LET'S TAKE THE STEPS INTO ACCOUNT:
1. TRACTION SEPARATION AND LOCALIZATION LAW
  - Functions to define :
  1. Calculate crack magnitude
  2. Define localization criterion
  3. Calculate traction
  
2. FINITE ELEMENT INTERPOLATION (TRACTION)


3. FUNCTION DEFINITIONS
   - Functions to define:
   1. All the K, G and H matrices.
   2.

4. ASSEMBLY OF K MATRICES
 - use the linalg function.

5. FINAL SOLUTION (INVOLVING THE USE STATIC CONDENSATION (GUYAN REDUCTION) TO REDUCE THE DEGREES OF FREEDOM  )
"""

#important library imports for maths and visualization
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.tri import Triangulation
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection

#LINEAR FEM PART
# ========================================================
# 1. GEOMETRY
nodes = np.array([
    [0, 0],  # Node 0
    [1, 0],  # Node 1
    [1, 1],  # Node 2
    [0, 1],  # Node 3
])

elements = np.array([
    [0, 1, 2],  # Element 1
    [2, 3, 0],  # Element 2
])

# ========================================================
# 2. MATERIAL PROPERTIES
E = 30e9
nu = 0.3

D = (E / ((1 + nu) * (1 - 2 * nu))) * np.array([
    [1 - nu, nu, 0],
    [nu, 1 - nu, 0],
    [0, 0, (1 - 2 * nu) / 2],
])

# ========================================================
# 3. FUNCTION DEFINITIONS - LINEAR FUNCTIONS

def calculate_area_triangle(element, nodes):
    coordinates = nodes[element]
    x0, y0 = coordinates[0]
    x1, y1 = coordinates[1]
    x2, y2 = coordinates[2]
    area = 0.5 * abs(x0 * (y1 - y2) + x1 * (y2 - y0) + x2 * (y0 - y1))
    return area

def calculate_B_matrix(element, nodes):
    coordinates = nodes[element]
    x0, y0 = coordinates[0]
    x1, y1 = coordinates[1]
    x2, y2 = coordinates[2]
    A = calculate_area_triangle(element, nodes)
    b = np.array([y1 - y2, y2 - y0, y0 - y1])
    c = np.array([x2 - x1, x0 - x2, x1 - x0])
    B = (1 / (2 * A)) * np.array([
        [b[0], 0, b[1], 0, b[2], 0],
        [0, c[0], 0, c[1], 0, c[2]],
        [c[0], b[0], c[1], b[1], c[2], b[2]]
    ])
    return B

def calculate_strains(elements, nodes, displacements):
    strains = []
    for element in elements:
        dof_map = np.concatenate([2 * element, 2 * element + 1])
        local_displacement = displacements[dof_map]
        B = calculate_B_matrix(element, nodes)
        epsilon = B @ local_displacement
        strains.append(epsilon)
    return np.array(strains)

def calculate_stress(strains, D):
    stresses = []
    for strain in strains:
        sigma = D @ strain
        stresses.append(sigma)
    return np.array(stresses)

# ====================================================
# 4. GLOBAL STIFFNESS MATRIX ASSEMBLY
number_of_dof = 2 * len(nodes)
K_global = np.zeros((number_of_dof, number_of_dof))

for element in elements:
    A = calculate_area_triangle(element, nodes)
    B = calculate_B_matrix(element, nodes)
    K_local = (B.T @ D @ B) * A
    dof_map = np.ravel([[2 * node, 2 * node + 1] for node in element])
    for i in range(6):
        for j in range(6):
            K_global[dof_map[i], dof_map[j]] += K_local[i, j]

# ====================================================
# 5. BOUNDARY CONDITIONS
F_global = np.zeros(number_of_dof)
F_global[2] = 1000.0
F_global[4] = 1000.0
fixed_dofs = [0, 1, 6, 7]

for dof in fixed_dofs:
    K_global[dof, :] = 0
    K_global[:, dof] = 0
    K_global[dof, dof] = 1
    F_global[dof] = 0

# ========================================================
# 6. LINEAR SOLUTIONS
displacements = np.linalg.solve(K_global, F_global)
#print("The shape of the displacements are", displacements.shape)

strains = calculate_strains(elements, nodes, displacements)
#print("The shape of the strains are", strains.shape)

stresses = calculate_stress(strains, D)
"""
print("The shape of the stresses are", stresses.shape)

print("The final Displacements are:", displacements)

print("The final stresses are: ", stresses)
"""


# ========================================================
# ========================================================
# ========================================================
# ========================================================

'''
HERE WE ADD THE EFEM COMPONENTS AND CARRY OUT THE NON-LINEAR ANALYSIS.
WE SEPARATE THE PARTS TO SUCCESSFULLY DISTINGUISH AND COMPARE THE RESULTS.
IN THE CASE OF FAILED IMPLEMENTATION OF A MATRIX, PLACEHOLDER VALUES WERE USED (THESE OBVIOUSLY AFFECT RESULTS
BUT ARE USED TO CHECK THE ALGORITHM).
'''
# ========================================================
# 1.EFEM COMPONENTS
'''
HERE WE DEFINE ALL THE MATRICES USED IN ROUBIN RESOLUTION METHODOLOGY, WHICH INCLUDES THE TRACTION SEPARATION LAW
AND LOCALIZATION CRITERION.
'''

# 1.1 - traction separation and localization laws
# ========================================================
# 1.1.1. MATERIAL PARAMETERS and TOOLS

# Yield stress in Pa
sigma_y = 30e6

# Fracture energy in N/m
G_f = 700

# Crack projection vector in 2D
np_vector = np.array([1.0, 0.0])

# ========================================================
# 1.1.2. LOCALIZATION CRITERION
#OUR EQUIVALENT STRESS SHOULD BE EQUAL TO THE GREATEST PRINCIPAL STRESS FROM THE FIRST CST ANALYSUS
#localization criterion
def localization_criterion(sigma_eq, sigma_y):
    phi_l = sigma_eq - sigma_y
    return phi_l

# ========================================================
# 1.1.3. CRACK OPENING AND TRACTION-SEPARATION LAW
#Crack opening magnitude
def compute_crack_opening_magnitude(sigma_eq, sigma_y, G_f):
    if sigma_eq <= sigma_y:
        return 0  # Elastic behavior, no crack opening

    # Small epsilon to avoid log of zero or negative values
    epsilon = 1e-12
    crack_magnitude = -(G_f / sigma_y) * np.log(np.maximum(1 - (sigma_eq / sigma_y), epsilon))
    return crack_magnitude


# 1.1.4. FINITE ELEMENT INTERPOLATION (TRACTION)
#Traction vector at the discontinuity interface.
def compute_traction(crack_magnitude, np_vector, sigma_y, G_f):
    # Hardening/softening function
    q = sigma_y * (1 - np.exp(-sigma_y / G_f * crack_magnitude))

    # Traction vector
    traction = crack_magnitude * np_vector * (sigma_y - q)
    return traction

# ========================================================
# USAGE

# GREATEST PRINCIPAL STRESS FROM CST ELEMENT ANALYSIS
'''
Can also use stresses[0] to retrieve the component.
'''
sigma_eq = 4.286e9

# Localization verification
phi_l = localization_criterion(sigma_eq, sigma_y)
if phi_l > 0:
    print("Crack opening has been detected.")

    # Compute crack opening magnitude
    crack_magnitude = compute_crack_opening_magnitude(sigma_eq, sigma_y, G_f)
    print("Crack Opening Magnitude [u]:", crack_magnitude)

    # Compute traction vector
    traction = compute_traction(crack_magnitude, np_vector, sigma_y, G_f)
    print("Traction Vector T:", traction)
else:
    print("Elastic behavior: no crack opening.")

# ========================================================
# 2.FUNCTION AND MATRIX DEFINITION
'''
HERE WE CREATE ALL THE K MATRICES TO BE PUT INTO THE FINAL EQUATION
Kbb, Kbw, Kbs, Kwb, kww, Kws, Ks*b, Ks*w, Ks*s, Kq
'''

def compute_K_bb(B, D):
    return B.T @ D @ B

def compute_K_bw(B, D):
    return B.T @ D @ Hw

'''
DIMENSION ISSUE
USE k_bs = np.eye(3) for now
def compute_k_bs(B, D, Gs, np_vector):
    return B.T @ D @ Gs @ np_vector
'''

def compute_K_ww(Hw, D):
    return Hw.T @ D @ Hw

'''
DIMENSION ISSUE
USE k_ws = np.eye(3) for now
def compute_K_ws(Hw, D, Gs, np_vector):
    return Hw @ D @ Gs @ np_vector
'''


def compute_K_ss(Gs, D):
    return Gs.T @ D @ Gs

def compute_Kb(B, D, Hs_star):
    return Hs_star.T @ D @ B


def compute_Kw(Hw, D, Hs_star):
    return Hs_star.T @ (D - D) @ Hw

def compute_Ks(Gs, D, Hs_star, np_vector):
    return Hs_star.T @ D @ Gs @ np_vector

def compute_Kq(crack_magnitude, sigma_y, G_f, size):
    exp_term = np.exp(-sigma_y * crack_magnitude / G_f)
    scalar_kq = (sigma_y**2 / G_f) * exp_term
    return scalar_kq * np.eye(size)  # Convert scalar to diagonal matrix of appropriate size


'''
here are all the symmetric operators
'''
def compute_Gw_matrix(normal_vector):
    #(PLACEHOLDER DATA!!!)
    weak_discontinuity= np.array([1, 0, 0])
    return np.outer(weak_discontinuity,normal_vector)

def compute_Gs_matrix():
    #TO TEST (PLACEHOLDER DATA!!!)
    strong_discontinuity= np.array([1, 0, 0])
    phi_e_grad = np.array([1, 0, 0])
    return np.outer(strong_discontinuity, phi_e_grad)

def compute_Hs_star_matrix(normal_vector):
    return np.outer(normal_vector, normal_vector)

normal_vector = np.array([1, 0, 0])

'''
def compute_strain(B, d, Gw, epsilon_jump, Gs, u_jump):
    return B @ d + Gw @ epsilon_jump + Gs @ u_jump

def compute_stress(D, strain):
    return D @ strain

#TRACTION VECTOR AT THE DISCONTINUITY
def compute_traction(Hs_star, stress):
    return Hs_star.T @ stress

'''


'''
THE COMPUTATION FUNCTIONS FOR THE SYSTEMS
'''
def compute_RHS(K_wb, K_sb, delta_d):
    #RHS = -[K_wb; K_sb] * delta_d
    rhs_weak = K_wb @ delta_d
    rhs_strong = K_sb @ delta_d


    # Concatenate to form (6,)
    return -np.hstack([rhs_weak, rhs_strong])

def compute_K_total(K_ww, K_ws, K_sw, K_ss, K_q):
    #Assemble the total stiffness matrix K_total.
    return np.block([
        [K_ww, K_ws],
        [K_sw, K_ss + K_q]
    ])

def compute_internal_rhs(f_int, f_ext):
    #RHS = -Σ(f_int - f_ext)."""
    return -np.sum(f_int - f_ext, axis=0)

def compute_K_global(K_ww, K_ws, K_sw, K_ss, K_q):
    #Assemble the global stiffness matrix
    return np.block([
        [K_ww, K_ws],
        [K_sw, K_ss + K_q]
    ])

def solve_inverted_system(K_total, RHS):
    #Delta = -K_total^{-1} * RHS
    return -np.linalg.inv(K_total) @ RHS

def solve_discontinuity_system(Hw, Gs, np_vector, C, delta_d, crack_magnitude, sigma_y, G_f):
    """Solve the coupled system for weak and strong discontinuities."""
    size = Hw.shape[0]  # Size of the system

    # Compute stiffness matrix components
    K_ww = compute_K_ww(Hw, C)
    #K_ws = compute_K_ws(Hw, C, Gs, np_vector)
    K_ws = np.eye(3)
    K_sw = K_ws.T  # Symmetry
    K_ss = compute_K_ss(Gs, C)
    K_q = compute_K_q(crack_magnitude, sigma_y, G_f, size)

    print("K_ww shape:", K_ww.shape)
    print("K_ws shape:", K_ws.shape)
    print("K_sw shape:", K_sw.shape)
    print("K_ss shape:", K_ss.shape)
    print("K_q  shape:", K_q.shape)

    # Assemble LHS
    K_total = compute_K_total(K_ww, K_ws, K_sw, K_ss, K_q)

    # Example placeholders for K_wb and K_sb
    K_wb = np.eye(size)  # Weak-bounded interaction (placeholder)
    K_sb = np.eye(size)  # Strong-bounded interaction (placeholder)

    # Compute RHS
    RHS = compute_RHS(K_wb, K_sb, delta_d)

    print("LHS shape:", K_total.shape)
    print("RHS shape:", RHS.shape)

    # Solve the system
    delta_discontinuities = solve_inverted_system(K_total, RHS)

    return delta_discontinuities, K_total, RHS

def solve_discontinuity_system_other_one(K_ww, K_ws, K_sw, K_ss, K_q, K_wb, K_sb, delta_d):
    #Weak and strong discontinuities
    #Assemble global stiffness matrix
    K_global = compute_K_global(K_ww, K_ws, K_sw, K_ss, K_q)

    #RHS
    RHS = compute_RHS(K_wb, K_sb, delta_d)

    # Discontinuity increments
    delta_discontinuities = np.linalg.solve(K_global, RHS)

    return delta_discontinuities, K_global, RHS

def solve_global_system(B, Hw, Gs, np_vector, D, f_int, f_ext, delta_d, crack_magnitude, sigma_y, G_f):
    #system for weak and strong discontinuities."""
    size = Hw.shape[0]  # Size of weak/strong matrices

    # Compute stiffness matrix components
    K_bb = compute_K_bb(B, D)
    K_bw = compute_K_bw(B, Hw, D)
    #K_bs = compute_K_bs(B, Gs, C, np_vector)
    K_bs = np.eye(3)
    K_ww = compute_K_ww(Hw, D)
    #K_ws = compute_K_ws(Hw, C, Gs, np_vector)
    K_ws = np.eye(3)
    K_ss = compute_K_ss(Gs, D)
    K_q = compute_Kq(crack_magnitude, sigma_y, G_f, size)

    print("K_ww shape:", K_ww.shape)
    print("K_ws shape:", K_ws.shape)
    print("K_sw shape:", K_ws.T.shape)
    print("K_ss shape:", K_ss.shape)
    print("K_q  shape:", K_q.shape)

    # Use corrected system for weak and strong discontinuities
    delta_discontinuities, K_global, RHS = solve_discontinuity_system_other_one(
        K_ww, K_ws, K_ws.T, K_ss, K_q, K_bw, K_bs, delta_d
    )

    return delta_discontinuities, K_global, RHS



# ========================================================
# 3.EFEM ASSEMBLY

# 3.1 LINEARIZATION OF EQUILIBRIUM EQUATION
# 3.1.1 LINEARIZATION SOLVER
def solve_phi_o(B, Hw, Gs, np_vector, Hs_star, phi_o, crack_magnitude, d):
    # Compute stiffness matrices
    #SYSTEM DIMENSION
    size = B.shape[0]
    K_b = compute_Kb(B, D, Hs_star)
    K_w = compute_Kw(Hw, D, Hs_star)
    K_s = compute_Ks(Gs, D, Hs_star, np_vector)
    K_q = compute_Kq(crack_magnitude, sigma_y, G_f, size)

    # Total stiffness matrix
    K_total = K_b + K_w + (K_s + K_q)

    # rHS DIMENSIONS MUST BE CORRECT

    rhs = np.full((size,), -phi_o)

    #D incrementAL
    delta = np.linalg.solve(K_total, rhs)

    return delta, K_total, rhs

# 3.2 LINEARIZATION OF STRONG DISCONTINUITY EQUATION

# 3.2.1 LINEARIZATION SOLVER



# 3.2.2 LINEARIZATION SOLVER FOR THE STATIC CONDENSATION PART
'''
[KWW    KWS ] DELTA [EPSILON] = - [KWB ] DELTA D
|KSW KSS+KQ | DELTA [U]           [KSB ]
'''

# ========================================================
# 4. NON-LINEAR SOLUTION
#

# SOLUTION FOR DISCONTINUITY  INCREMENTS
delta_discontinuities, K_total, RHS = solve_discontinuity_system(
    Hw, Gs, np_vector, C, delta_d, crack_magnitude, sigma_y, G_f)


print("Delta Discontinuities (Weak and Strong):", delta_discontinuities)
print("LHS Matrix:\n", K_total)
print("RHS Vector:\n", RHS)

#TOTAL GLOBAL INVERSE SOLUTION
delta_discontinuities, K_global, RHS = solve_global_system(B, Hw, Gs, np_vector, C, f_int, f_ext, delta_d, crack_magnitude, sigma_y, G_f)

print("Delta Discontinuities (Weak and Strong):", delta_discontinuities)
print("K_global Matrix:\n", K_global)
print("RHS Vector:\n", RHS)

# ========================================================
# 5. TOTAL SOLUTION

# ========================================================
# 6. PLOTS AND VISUALIZATION

