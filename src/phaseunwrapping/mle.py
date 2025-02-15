import numpy as np
from scipy.sparse.linalg import aslinearoperator
import scipy.sparse as sps

from .util import wrap_function, build_1d_first_order_grad, upsampling_matrix, build_2d_first_order_grad, banded_cholesky_factor
from .cg import relative_residual_cg



def mle_1d(psi, weights=None):
    """Given a 1D wrapped phase vector psi, computes the MLE estimator corresponding to the D2 data fidelity term.
    
    psi: the wrapped phase.
    weights: weighint for the D2 penalty function.

    """

    # Figure out shape
    n = len(psi)

    # Build F matrix
    F = build_1d_first_order_grad(n, boundary="none")

    # Make $\phi_1$
    phi1 = np.zeros(n)
    phi1[0] = psi[0]

    # Build the undersampling matrix
    P = np.eye(n)[1:,:].T

    # Set initial weights
    if weights is None:
        weights = np.ones(F.shape[0])
    else:
        assert len(weights) == len(psi), "psi and weight vector must have same length!"

    # rhs vector
    rhs = P.T @ F.T @ np.diag(weights) @ ( wrap_function(F @ psi) - (F @ phi1) )

    # Q matrix
    Q = P.T @ F.T @ np.diag(weights) @ F @ P  

    # Solve system for answer
    phi2 = np.linalg.solve(Q, rhs)

    # Append first entry
    reconstructed_phi = np.zeros(n)
    reconstructed_phi[1:] = phi2
    reconstructed_phi[0] = psi[0]

    return reconstructed_phi



def mle_2d_banded_cholesky(psi, weights=None):
    """
    """
    M, N = psi.shape

    # Get flattened version of psi
    psi_flatten = psi.flatten()

    # Gradient ops
    Fx, Fy = build_2d_first_order_grad(M, N, boundary="none")

    if weights is None:
        weights = np.ones(Fx.shape[0])
    else:
        assert len(weights) == len(psi), "psi and weight vector must have same length!"
    weights = weights.flatten()

    P = upsampling_matrix(len(psi_flatten) - 1, sparse=True)

    phi1 = np.zeros(len(psi_flatten))
    phi1[0] = psi_flatten[0]

    Dweights = sps.diags(weights)

    # rhs vector
    rhs = P.T @ Fx.T @ Dweights @ ( wrap_function(Fx @ psi_flatten) - (Fx @ phi1) ) + P.T @ Fy.T @ Dweights @ ( wrap_function(Fy @ psi_flatten) - (Fy @ phi1) )

    # Q matrix
    Q = P.T @ Fx.T @ Dweights @ Fx @ P  + P.T @ Fy.T @ Dweights @ Fy @ P

    # banded cholesky
    L, superlu = banded_cholesky_factor(Q)

    # Compute mean
    sol = superlu.solve(rhs)

    # Include initial phase value
    reconstructed_phi = np.zeros(len(psi_flatten))
    reconstructed_phi[1:] = sol
    reconstructed_phi[0] = psi_flatten[0]
    reconstructed_phi = reconstructed_phi.reshape((M,N))

    return reconstructed_phi

    


def mle_2d(psi, weights=None, solve_method="iterative", cg_tol=1e-4, cg_maxits=None, cg_x0=None):

    valid_methods = ["iterative", "direct"]
    assert solve_method in valid_methods, f"invalid solve method, must be in {valid_methods}"

    M, N = psi.shape

    # Get flattened version of psi
    psi_flatten = psi.flatten()

    # Gradient ops
    print("Building grad ops")
    Fx, Fy = build_2d_first_order_grad(M, N, boundary="none")

    if solve_method == "iterative":
        cg_maxits = Fx.shape[1]

    # Set initial weights
    #might have to adjust this code if we are not looking at N by N image
    if weights is None:
        weights = np.ones(Fx.shape[0])
    else:
        assert len(weights) == len(psi), "psi and weight vector must have same length!"
    
    print("building P")
    P = upsampling_matrix(len(psi_flatten) - 1, sparse=True)
    
    phi1 = np.zeros(len(psi_flatten))
    phi1[0] = psi_flatten[0]

    Dweights = sps.diags(weights)
   
    # rhs vector
    print("building rhs")
    rhs = P.T @ (Fx.T @ ( Dweights @ ( wrap_function(Fx @ psi_flatten) - (Fx @ phi1) ) ) ) + P.T @ ( Fy.T @ ( Dweights @ ( wrap_function(Fy @ psi_flatten) - (Fy @ phi1) ) ) )

    # Q matrix
    print("building Q")
    Q = aslinearoperator(P.T) @ aslinearoperator(Fx.T) @ aslinearoperator(Dweights) @ aslinearoperator(Fx) @ aslinearoperator(P)  + aslinearoperator(P.T) @ aslinearoperator(Fy.T) @ aslinearoperator(Dweights) @ aslinearoperator(Fy) @ aslinearoperator(P)
   
    print("starting solve")
    # Solve system for answer
    if solve_method == "direct":
        phi2 = np.linalg.solve(Q, rhs) # O(N^3)
    elif solve_method == "iterative":
        Q = aslinearoperator(Q)
        phi2 = relative_residual_cg(Q, rhs, eps=cg_tol, maxits=cg_maxits, x0=cg_x0) # conjugate gradient O(\kappa N)
        print(phi2["iterations"])
        phi2 = phi2["x"]
        
    # Append first entry
    reconstructed_phi = np.zeros(len(psi_flatten))
    reconstructed_phi[1:] = phi2
    reconstructed_phi[0] = psi_flatten[0]

    return reconstructed_phi
    



















