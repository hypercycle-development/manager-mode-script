from typing import List, Dict, TypedDict


class Deposit(TypedDict):
    _id: str
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
    },
)


class GetTransferResponse(TypedDict):
    nodes: Dict[str, List[TransferTx]]
    refunds: List[TransferTx]
