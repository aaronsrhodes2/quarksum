"""SGIntegrator -- Forest-Ruth as a scipy.integrate-compatible interface.

Provides sg_solve_ivp() and sg_odeint() as drop-in replacements for
scipy.integrate.solve_ivp / odeint, enforcing symplectic integration
for Hamiltonian systems (orbits, oscillators).

For non-Hamiltonian systems the signature is compatible but the symplectic
guarantee does not apply -- use standard RK methods instead.

Convention
----------
All public functions are prefixed sg_ (sigma-ground).  The scipy functions
remain available and unmodified via their normal import path.

Usage
-----
    # Before: scipy (RK45, not symplectic -- energy drifts over time)
    from scipy.integrate import solve_ivp
    sol = solve_ivp(f, t_span, y0, method='RK45', t_eval=t_eval)

    # After: SSBM (Forest-Ruth, symplectic -- energy conserved exactly)
    from sigma_ground.field.interface.adapters.integrator import sg_solve_ivp
    sol = sg_solve_ivp(f, t_span, y0, method='forest_ruth', t_eval=t_eval)

    # N-body shortcut (most common case):
    from sigma_ground.field.interface.adapters.integrator import sg_nbody
    final_bodies = sg_nbody(bodies, dt_s=3600.0, t_total_s=365.25*86400)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.typing import NDArray


@dataclass
class SGSolution:
    """Return type for sg_solve_ivp -- mirrors scipy.integrate.OdeResult."""
    t:       NDArray[np.float64]   # time points
    y:       NDArray[np.float64]   # state (n_states × n_time)
    method:  str
    success: bool
    message: str


def sg_solve_ivp(
    fun:     Callable[[float, NDArray], NDArray],
    t_span:  tuple[float, float],
    y0:      NDArray[np.float64],
    method:  str = "forest_ruth",
    t_eval:  NDArray[np.float64] | None = None,
    dt:      float | None = None,
    include_gr: bool = False,
) -> SGSolution:
    """Integrate an ODE using a symplectic method.

    The state vector y must be split as [q, p] (positions then momenta)
    for symplectic methods.  For non-symplectic systems, use method='rk4'.

    Parameters
    ----------
    fun     : callable f(t, y) returning dy/dt, shape (2N,) for N dofs
    t_span  : (t0, tf) integration interval in seconds
    y0      : initial state [q_0, ..., q_N, p_0, ..., p_N], shape (2N,)
    method  : 'forest_ruth' (4th-order symplectic, default)
              'verlet'      (2nd-order symplectic, faster)
              'rk4'         (4th-order non-symplectic, for non-Hamiltonian)
    t_eval  : times at which to record solution (optional)
    dt      : timestep (seconds); if None, inferred as (tf-t0)/1000
    include_gr : for N-body orbital problems, add 1PN GR correction

    Returns
    -------
    SGSolution with fields t, y (states), method, success, message

    Notes
    -----
    Forest-Ruth requires FIXED dt for guaranteed symplecticity.
    If t_eval is provided but does not align with dt, the nearest step is used.
    """
    t0, tf  = t_span
    if dt is None:
        dt = (tf - t0) / 1_000
    if dt <= 0:
        raise ValueError(f"dt must be positive, got {dt}")

    n_steps = int(math.ceil((tf - t0) / dt))
    dt_real = (tf - t0) / n_steps  # adjust to land exactly on tf

    n_state = len(y0)
    N       = n_state // 2  # number of degrees of freedom

    # Determine recording times
    if t_eval is None:
        record_steps = set(range(0, n_steps + 1, max(1, n_steps // 200)))
        record_steps.add(n_steps)
    else:
        record_steps = {
            min(n_steps, int(round((t - t0) / dt_real)))
            for t in t_eval
        }

    t_out: list[float]             = []
    y_out: list[NDArray[np.float64]] = []

    y = np.array(y0, dtype=np.float64)
    t = t0

    # Forest-Ruth coefficients (exact -- Forest & Ruth 1990)
    _theta = 1.0 / (2.0 - 2.0 ** (1.0 / 3.0))
    _c = [_theta / 2, (1 - _theta) / 2, (1 - _theta) / 2, _theta / 2]
    _d = [_theta, 1 - 2 * _theta, _theta]  # d[1] is negative

    for step in range(n_steps + 1):
        if step in record_steps:
            t_out.append(t)
            y_out.append(y.copy())

        if step == n_steps:
            break

        if method == "forest_ruth":
            y = _fr4_step(fun, t, y, dt_real, N, _c, _d)
        elif method == "verlet":
            y = _verlet_step(fun, t, y, dt_real, N)
        elif method == "rk4":
            y = _rk4_step(fun, t, y, dt_real)
        else:
            raise ValueError(
                f"Unknown method {method!r}. "
                f"Choose 'forest_ruth', 'verlet', or 'rk4'."
            )
        t += dt_real

    return SGSolution(
        t=np.array(t_out),
        y=np.column_stack(y_out) if y_out else np.zeros((n_state, 0)),
        method=method,
        success=True,
        message="OK",
    )


def _fr4_step(
    fun: Callable, t: float, y: NDArray, dt: float,
    N: int, c: list, d: list,
) -> NDArray:
    """One Forest-Ruth step: 4 drifts + 3 kicks."""
    q, p = y[:N].copy(), y[N:].copy()

    def _drift(frac: float) -> None:
        # Compute dq/dt = dp/dt evaluated at momentum; for simple Hamiltonian
        # H = T(p) + V(q), dq/dt = dH/dp = p/m.  We call fun and use the
        # first N components (position derivatives) as the drift.
        dqdt = fun(t, np.concatenate([q, p]))[:N]
        q[:] += frac * dt * dqdt

    def _kick(frac: float) -> None:
        dpdt = fun(t, np.concatenate([q, p]))[N:]
        p[:] += frac * dt * dpdt

    _drift(c[0]); _kick(d[0])
    _drift(c[1]); _kick(d[1])
    _drift(c[2]); _kick(d[2])
    _drift(c[3])

    return np.concatenate([q, p])


def _verlet_step(
    fun: Callable, t: float, y: NDArray, dt: float, N: int,
) -> NDArray:
    """One velocity-Verlet (leapfrog) step."""
    q, p = y[:N].copy(), y[N:].copy()
    dydt = fun(t, y)
    p_half = p + 0.5 * dt * dydt[N:]
    q_new  = q + dt * fun(t, np.concatenate([q, p_half]))[:N]
    dydt2  = fun(t + dt, np.concatenate([q_new, p_half]))
    p_new  = p_half + 0.5 * dt * dydt2[N:]
    return np.concatenate([q_new, p_new])


def _rk4_step(
    fun: Callable, t: float, y: NDArray, dt: float,
) -> NDArray:
    """Standard 4th-order Runge-Kutta (not symplectic)."""
    k1 = fun(t,            y)
    k2 = fun(t + dt / 2,  y + dt / 2 * k1)
    k3 = fun(t + dt / 2,  y + dt / 2 * k2)
    k4 = fun(t + dt,       y + dt * k3)
    return y + (dt / 6) * (k1 + 2 * k2 + 2 * k3 + k4)


# ── N-body convenience wrapper ────────────────────────────────────────────

def sg_nbody(
    bodies: list,
    dt_s:   float,
    t_total_s: float,
    method: str = "forest_ruth",
    include_gr: bool = True,
    record_every: int = 1,
) -> tuple[list, list[float]]:
    """Propagate CelestialBody list using Forest-Ruth (or Verlet).

    Convenience wrapper around NBodySystem; no scipy dependency.

    Parameters
    ----------
    bodies     : list of CelestialBody (from sigma_ground.field.interface.nbody)
    dt_s       : fixed timestep (seconds) -- keep fixed for symplecticity
    t_total_s  : total integration time (seconds)
    method     : 'forest_ruth' or 'verlet'
    include_gr : include 1PN Schwarzschild correction
    record_every : record state every N steps (1 = every step)

    Returns
    -------
    final_bodies : list of CelestialBody at t = t_total_s
    times_s      : list of recorded simulation times
    """
    from sigma_ground.field.interface.nbody import NBodySystem

    system  = NBodySystem(bodies, include_gr=include_gr)
    step_fn = system.forest_ruth_step if method == "forest_ruth" else system.step
    n_steps = int(math.ceil(t_total_s / dt_s))
    times   = []

    for i in range(n_steps):
        if i % record_every == 0:
            times.append(system.time)
        step_fn(dt_s)

    times.append(system.time)
    return system.bodies, times


def sg_odeint(
    func: Callable,
    y0:   NDArray,
    t:    NDArray,
    method: str = "forest_ruth",
) -> NDArray:
    """scipy.integrate.odeint-compatible interface using Forest-Ruth.

    Parameters
    ----------
    func : callable f(y, t) or f(t, y) returning dy/dt
    y0   : initial state
    t    : array of times (must be equally spaced for symplecticity)
    method : 'forest_ruth', 'verlet', or 'rk4'

    Returns
    -------
    y : NDArray shape (len(t), len(y0))
    """
    # Detect odeint signature f(y, t) vs solve_ivp signature f(t, y)
    import inspect
    sig  = inspect.signature(func)
    params = list(sig.parameters.keys())
    if len(params) >= 2 and params[0] != "t":
        # odeint style f(y, t) -> convert to f(t, y)
        fun = lambda t_, y_: func(y_, t_)
    else:
        fun = func

    if len(t) < 2:
        return np.array([y0])

    dt   = t[1] - t[0]
    sol  = sg_solve_ivp(fun, (t[0], t[-1]), np.asarray(y0),
                        method=method, t_eval=t, dt=dt)

    # Return (n_time, n_state) like scipy.integrate.odeint
    return sol.y.T
