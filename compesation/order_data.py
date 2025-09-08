from typing import Dict
from app_types import UserNodeData


def get_remaining_as_usdc(
    cost_in_usd: int, cost_in_hypc: int, remaining_hypc: int
) -> int:
    # cost_in_usd === cost_in_hypc
    #       X usd    === remaining_hypc

    # Assume usd==usdc
    return int((remaining_hypc * cost_in_usd) / cost_in_hypc)


def calculate_end_balance(data: Dict[str, UserNodeData]):
    result = {}

    for node_name, user_data in data.items():
        # Open a new entry for this node
        result[node_name] = {
            "hypc": 0,
            "usdc": 0,
        }

        # Combine and sort registered deposits and interactions by timestamp
        events = []

        # Add registered deposits
        for deposit in user_data.get("registered_deposits", []):
            events.append(
                {
                    "timestamp": int(deposit["timeStamp"]),
                    "type": "deposit",
                    "token": deposit["tokenSymbol"],
                    "amount": int(deposit["value"]),
                }
            )

        # Add interactions
        for interaction in user_data.get("user_interactions", []):
            # Skip interactions with no cost
            if not interaction.get("cost"):
                continue

            events.append(
                {
                    "timestamp": interaction["timestamp"],
                    "type": "interaction",
                    "usd_cost": int(interaction["cost"][0]["used"]),
                    "hypc_used": int(
                        interaction["value_used"].get("HyPC", {"used": 0})["used"]
                    ),
                    # usdc used most likely is 0, but just added for safety
                    "usdc_used": int(
                        interaction["value_used"].get("USDC", {"used": 0})["used"]
                    ),
                }
            )

        # Sort events by timestamp
        events.sort(key=lambda x: x["timestamp"])

        for event in events:
            if event["type"] == "deposit":
                token = event["token"]
                amount = event["amount"]

                if token == "USDC":
                    result[node_name]["usdc"] += amount
                elif token == "HyPC":
                    result[node_name]["hypc"] += amount
                else:
                    # Not gonna happen but safe case
                    pass
            elif event["type"] == "interaction":
                usd_cost = event["usd_cost"]
                hypc_used = event["hypc_used"]

                if result[node_name]["hypc"] >= hypc_used:
                    # This menas, that no usdc was needed
                    result[node_name]["hypc"] -= hypc_used
                else:
                    # Getting amount remaining as USDC equivalent
                    remaining_hypc = hypc_used - result[node_name]["hypc"]
                    usdc_equivalent = get_remaining_as_usdc(
                        usd_cost, hypc_used, remaining_hypc
                    )

                    # Updating balances
                    result[node_name]["hypc"] = 0  # No remaining hypc

                    # If the interaction was made, then we got the cost, but maybe our calculation is off so we can safetly check here
                    result[node_name]["usdc"] = max(
                        0, result[node_name]["usdc"] - usdc_equivalent
                    )

    return result
