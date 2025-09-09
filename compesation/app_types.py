from typing import List, Dict, TypedDict


class Deposit(TypedDict):
    _id: str
    currency_type: str
    registered_time: float
    sender: str
    value: int
    status: str


class DepositResponse(TypedDict):
    data: List[Deposit]
    total_count: int


TransferTx = TypedDict(
    "TransferTx",
    {
        "hash": str,
        "blockNumber": str,
        "timeStamp": str,
        "from": str,
        "to": str,
        "value": str,
        "tokenSymbol": str,
    },
)


class GetTransferResponse(TypedDict):
    nodes: Dict[str, List[TransferTx]]
    refunds: List[TransferTx]


class ValueUsedEntry(TypedDict):
    used: int


class CurrencyUsedEntry(TypedDict):
    currency: str
    used: int


class ValueUsed(TypedDict, total=False):
    HyPC: ValueUsedEntry
    USDC: ValueUsedEntry


class Interaction(TypedDict):
    timestamp: float
    value_used: ValueUsed
    uri: str
    hypc_user: str
    tx_sender: str
    status_code: int
    cost: List[CurrencyUsedEntry]


class UserNodeData(TypedDict):
    user_balance: Dict[str,int] | None
    user_interactions: List[Interaction]
    registered_deposits: List[TransferTx]
    unregistered_deposits: List[TransferTx]
    
class EndBalanceResponse(TypedDict):
    HyPC: int
    USDC: int
