"""Parameter generation for query parameterization."""

import random
from typing import Any

from harness.config import ParameterSpec


def generate_params(param_config: dict[str, ParameterSpec] | None) -> dict[str, Any]:
    """Generate parameter values for query substitution.

    Supports random integer generation and random choice from list.

    Args:
        param_config: Parameter specification dict (name -> ParameterSpec)

    Returns:
        Dict of parameter name -> generated value

    Examples:
        >>> specs = {
        ...     "user_id": ParameterSpec(type="random_int", min=1, max=1000),
        ...     "status": ParameterSpec(type="random_choice", values=["active", "inactive"])
        ... }
        >>> params = generate_params(specs)
        >>> # Returns e.g., {"user_id": 456, "status": "active"}
    """
    if not param_config:
        return {}

    params = {}

    for name, spec in param_config.items():
        if spec.type == "random_int":
            # Generate random integer in range [min, max]
            if spec.min is None or spec.max is None:
                raise ValueError(
                    f"Parameter '{name}': random_int requires both min and max"
                )
            params[name] = random.randint(spec.min, spec.max)

        elif spec.type == "random_choice":
            # Choose random value from list
            if not spec.values:
                raise ValueError(
                    f"Parameter '{name}': random_choice requires non-empty values list"
                )
            params[name] = random.choice(spec.values)

        else:
            raise ValueError(f"Parameter '{name}': unknown type '{spec.type}'")

    return params
