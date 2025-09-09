from typing import List, Dict, Any
from app_types import (
    EndBalanceResponse,
    UserNodeData,
    DepositResponse,
    GetTransferResponse,
    TransferTx,
    UserNodeData,
    Interaction,
)


def get_remaining_as_usdc(
    cost_in_usd: int, cost_in_hypc: int, remaining_hypc: int
) -> int:
    # cost_in_usd === cost_in_hypc
    #       X usd    === remaining_hypc

    # Assume usd==USDC
    return int((remaining_hypc * cost_in_usd) / cost_in_hypc)


def calculate_end_balance_per_node(
    data: Dict[str, UserNodeData],
) -> Dict[str, EndBalanceResponse]:
    result = {}

    for node_name, user_data in data.items():
        # Open a new entry for this node
        result[node_name] = {
            "HyPC": 0,
            "USDC": 0,
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
                    # USDC used most likely is 0, but just added for safety
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
                    result[node_name]["USDC"] += amount
                elif token == "HyPC":
                    result[node_name]["HyPC"] += amount
                else:
                    # Not gonna happen but safe case
                    pass
            elif event["type"] == "interaction":
                usd_cost = event["usd_cost"]
                hypc_used = event["hypc_used"]

                if result[node_name]["HyPC"] >= hypc_used:
                    # This menas, that no USDC was needed
                    result[node_name]["HyPC"] -= hypc_used
                else:
                    # Getting amount remaining as USDC equivalent
                    remaining_hypc = hypc_used - result[node_name]["HyPC"]
                    usdc_equivalent = get_remaining_as_usdc(
                        usd_cost, hypc_used, remaining_hypc
                    )

                    # Updating balances
                    result[node_name]["HyPC"] = 0  # No remaining HyPC

                    # If the interaction was made, then we got the cost, but maybe our calculation is off so we can safetly check here
                    result[node_name]["USDC"] = max(
                        0, result[node_name]["USDC"] - usdc_equivalent
                    )

    return result


def calculate_total_balance(
    user_node_data: Dict[str, UserNodeData],
    calculated_balances: Dict[str, EndBalanceResponse],
    refunds_txs: List[TransferTx],
):
    # Sum all the balances into just one. We only will take care of the USDC.
    # Only get the Max between the balances comming from the user node data and calculated balacnes for each node
    total_balance = 0

    for node_name in calculated_balances:
        user_calculated_balance = calculated_balances[node_name]["USDC"]

        user_balance_data = user_node_data[node_name]["user_balance"]
        user_node_balance = 0

        if user_balance_data is not None:
            user_balance_data.get("USDC", 0)

        total_balance += max(user_calculated_balance, user_node_balance)

    unregistered_deposits: List[TransferTx] = []

    for data in user_node_data.values():
        to_save = [
            tx for tx in data["unregistered_deposits"] if tx["tokenSymbol"] == "USDC"
        ]

        unregistered_deposits.extend(to_save)

    for deposit in unregistered_deposits:
        total_balance += int(deposit["value"])

    for refunds in refunds_txs:
        if refunds["tokenSymbol"] == "USDC":
            total_balance -= int(refunds["value"])

    return total_balance
