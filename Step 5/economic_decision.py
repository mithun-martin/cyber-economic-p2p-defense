"""
Step 5: Economic-Aware Mitigation Decision Engine
Core decision logic computing risk-adjusted expected economic losses and emitting ALLOW/MITIGATE actions.

Decision Rule:
  E[Loss(ALLOW)]    = p_attack * C_FN
  E[Loss(MITIGATE)] = (1 - p_attack) * C_FP + C_M

Action:
  MITIGATE if E[Loss(ALLOW)] > E[Loss(MITIGATE)]
  ALLOW    otherwise (including exact ties)

Supports both scalar and vectorized (NumPy / pandas) inputs.
Strictly validates probability bounds and non-negative finite cost inputs.
"""

from typing import Dict, Tuple, Union
import numpy as np
import pandas as pd


class DecisionAction:
    ALLOW = "ALLOW"
    MITIGATE = "MITIGATE"


def validate_scalar_inputs(
    p_attack: float,
    c_fn: float,
    c_fp: float,
    c_m: float
) -> None:
    """Validates scalar inputs, raising ValueError or TypeError on invalid parameters."""
    for name, val in [("p_attack", p_attack), ("C_FN", c_fn), ("C_FP", c_fp), ("C_M", c_m)]:
        if val is None:
            raise ValueError(f"Missing required input: {name} cannot be None.")
        if not isinstance(val, (int, float, np.floating, np.integer)):
            raise TypeError(f"Invalid type for {name}: expected float or int, got {type(val).__name__}.")
        if np.isnan(val) or np.isinf(val):
            raise ValueError(f"Non-finite value for {name}: received {val}.")

    if not (0.0 <= p_attack <= 1.0):
        raise ValueError(f"Probability out of bounds: p_attack must be in [0.0, 1.0], received {p_attack}.")
    if c_fn < 0.0:
        raise ValueError(f"Negative cost prohibited: C_FN must be >= 0.0, received {c_fn}.")
    if c_fp < 0.0:
        raise ValueError(f"Negative cost prohibited: C_FP must be >= 0.0, received {c_fp}.")
    if c_m < 0.0:
        raise ValueError(f"Negative cost prohibited: C_M must be >= 0.0, received {c_m}.")


def evaluate_decision_scalar(
    p_attack: float,
    c_fn: float,
    c_fp: float,
    c_m: float = 0.0
) -> Dict[str, Union[float, str]]:
    """
    Evaluates expected economic loss and emits decision for a single scalar observation.
    
    Returns dict:
      - expected_loss_allow: float
      - expected_loss_mitigate: float
      - decision: str ('ALLOW' or 'MITIGATE')
      - decision_reason: str
    """
    validate_scalar_inputs(p_attack, c_fn, c_fp, c_m)

    loss_allow = float(p_attack * c_fn)
    loss_mitigate = float((1.0 - p_attack) * c_fp + c_m)

    # Tie-breaking rule: ALLOW on tie to avoid unnecessary market disruption
    if abs(loss_allow - loss_mitigate) < 1e-12:
        decision = DecisionAction.ALLOW
        reason = f"ALLOW (Tie): expected losses equal ({loss_allow:.4f})"
    elif loss_allow > loss_mitigate:
        decision = DecisionAction.MITIGATE
        reason = f"MITIGATE: expected loss allow ({loss_allow:.4f}) > mitigate ({loss_mitigate:.4f})"
    else:
        decision = DecisionAction.ALLOW
        reason = f"ALLOW: expected loss allow ({loss_allow:.4f}) < mitigate ({loss_mitigate:.4f})"

    return {
        "expected_loss_allow": loss_allow,
        "expected_loss_mitigate": loss_mitigate,
        "decision": decision,
        "decision_reason": reason
    }


def evaluate_decision_vectorized(
    p_attack: Union[np.ndarray, pd.Series],
    c_fn: Union[float, np.ndarray, pd.Series],
    c_fp: Union[float, np.ndarray, pd.Series],
    c_m: Union[float, np.ndarray, pd.Series] = 0.0
) -> Dict[str, Union[np.ndarray, list]]:
    """
    Evaluates expected economic loss and emits decisions for vectorized/batched arrays.
    
    Accepts arrays or scalar costs broadcasted across p_attack.
    Returns dict with NumPy arrays:
      - expected_loss_allow: np.ndarray (float64)
      - expected_loss_mitigate: np.ndarray (float64)
      - decision: np.ndarray (str)
      - decision_reason: list of str
    """
    p_arr = np.asarray(p_attack, dtype=np.float64)
    if not np.all(np.isfinite(p_arr)):
        raise ValueError("Vectorized input p_attack contains non-finite values (NaN or Inf).")
    if np.any(p_arr < 0.0) or np.any(p_arr > 1.0):
        raise ValueError("Vectorized input p_attack contains values outside [0.0, 1.0].")

    # Broadcast costs if scalar
    fn_arr = np.asarray(c_fn, dtype=np.float64)
    fp_arr = np.asarray(c_fp, dtype=np.float64)
    m_arr = np.asarray(c_m, dtype=np.float64)

    for name, arr in [("C_FN", fn_arr), ("C_FP", fp_arr), ("C_M", m_arr)]:
        if not np.all(np.isfinite(arr)):
            raise ValueError(f"Vectorized cost input {name} contains non-finite values (NaN or Inf).")
        if np.any(arr < 0.0):
            raise ValueError(f"Vectorized cost input {name} contains negative values.")

    loss_allow = p_arr * fn_arr
    loss_mitigate = (1.0 - p_arr) * fp_arr + m_arr

    # Decision mask: True = MITIGATE, False = ALLOW
    mitigate_mask = loss_allow > loss_mitigate
    tie_mask = np.isclose(loss_allow, loss_mitigate, atol=1e-12)
    # On tie, force False (ALLOW)
    mitigate_mask = mitigate_mask & (~tie_mask)

    decisions = np.where(mitigate_mask, DecisionAction.MITIGATE, DecisionAction.ALLOW)

    # Format reasons
    reasons = []
    for la, lm, dec, is_tie in zip(loss_allow.flat, loss_mitigate.flat, decisions.flat, tie_mask.flat):
        if is_tie:
            reasons.append(f"ALLOW (Tie): expected losses equal ({la:.4f})")
        elif dec == DecisionAction.MITIGATE:
            reasons.append(f"MITIGATE: expected loss allow ({la:.4f}) > mitigate ({lm:.4f})")
        else:
            reasons.append(f"ALLOW: expected loss allow ({la:.4f}) < mitigate ({lm:.4f})")

    if isinstance(p_attack, pd.Series):
        return {
            "expected_loss_allow": pd.Series(loss_allow, index=p_attack.index),
            "expected_loss_mitigate": pd.Series(loss_mitigate, index=p_attack.index),
            "decision": pd.Series(decisions, index=p_attack.index),
            "decision_reason": pd.Series(reasons, index=p_attack.index)
        }

    return {
        "expected_loss_allow": loss_allow,
        "expected_loss_mitigate": loss_mitigate,
        "decision": decisions,
        "decision_reason": reasons
    }


def make_economic_decision(
    p_attack: Union[float, np.ndarray, pd.Series],
    c_fn: Union[float, np.ndarray, pd.Series],
    c_fp: Union[float, np.ndarray, pd.Series],
    c_m: Union[float, np.ndarray, pd.Series] = 0.0
) -> Dict[str, Union[float, str, np.ndarray, pd.Series, list]]:
    """
    Unified entrypoint for the economic decision engine.
    Automatically routes scalar inputs to scalar evaluator and arrays to vectorized evaluator.
    """
    if np.isscalar(p_attack):
        return evaluate_decision_scalar(float(p_attack), float(c_fn), float(c_fp), float(c_m))
    return evaluate_decision_vectorized(p_attack, c_fn, c_fp, c_m)


def make_fixed_threshold_decision(
    p_attack: Union[float, np.ndarray, pd.Series],
    threshold: float = 0.50
) -> Dict[str, Union[str, np.ndarray, pd.Series]]:
    """
    Baseline fixed-threshold decision policy:
      MITIGATE if p_attack >= threshold
      ALLOW    otherwise
    """
    if not (0.0 <= threshold <= 1.0):
        raise ValueError(f"Threshold must be in [0.0, 1.0], received {threshold}.")

    if np.isscalar(p_attack):
        if not (0.0 <= p_attack <= 1.0) or np.isnan(p_attack):
            raise ValueError(f"Invalid p_attack: {p_attack}")
        dec = DecisionAction.MITIGATE if p_attack >= threshold else DecisionAction.ALLOW
        reason = f"Fixed threshold {threshold:.2f}: p_attack ({p_attack:.4f}) {' >= ' if dec == DecisionAction.MITIGATE else ' < '} threshold"
        return {"decision": dec, "decision_reason": reason}

    p_arr = np.asarray(p_attack, dtype=np.float64)
    if not np.all(np.isfinite(p_arr)) or np.any(p_arr < 0.0) or np.any(p_arr > 1.0):
        raise ValueError("Invalid probabilities in vectorized p_attack.")

    decisions = np.where(p_arr >= threshold, DecisionAction.MITIGATE, DecisionAction.ALLOW)
    reasons = [
        f"Fixed threshold {threshold:.2f}: p_attack ({p:.4f}) {' >= ' if d == DecisionAction.MITIGATE else ' < '} threshold"
        for p, d in zip(p_arr.flat, decisions.flat)
    ]

    if isinstance(p_attack, pd.Series):
        return {
            "decision": pd.Series(decisions, index=p_attack.index),
            "decision_reason": pd.Series(reasons, index=p_attack.index)
        }
    return {"decision": decisions, "decision_reason": reasons}
