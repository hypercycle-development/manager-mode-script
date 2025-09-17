USDC_CONTRACT_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
HYPC_CONTRACT_ADDRESS = "0xeA7B7DC089c9a4A916B5a7a37617f59fD54e37E4"
REFUND_WALLET_ADDRESSES = [
    "0x3Cb705Dad71DfeaFa928963B6fF21bF99FF4C2b9",
    "0x181615a6889e7cCD2DD4bf4375836351060704Db",
]
REFUND_WALLET_ADDRESSES_SET = {addr.lower() for addr in REFUND_WALLET_ADDRESSES}

tranche1_addresses_gist_id = "1d91a306014cab0eefea297feab97e54"
ETHERSCAN_API_KEY = "5BX4F2DJK5GXBEK62TCMFM9P86WD3RUFHR"

MAX_TIMESTAMP_UTC = 1754006400  # August 1, 2025
MAX_BLOCK_NUMBER = 23042514  # Exact block number for August 1, 2025

# Merklizer Mainnet
MERKLIZER_URL = "18.216.251.149:8003"


HTS_NODES = {
    "AWSTillingService1": {
        "url": "https://hyperpg.site/forward/52.73.19.138/8000",
        "address": "0x9F0c0D8759D8d14E8BE31919EA2739a6200B26B8",
    },
    "AWSTillingService2": {
        "url": "https://hyperpg.site/forward/18.236.42.238/8000",
        "address": "0x3b8B4E51A7AA83a848a355D234Df19A0391C933b",
    },
    "AWSTillingService3": {
        "url": "https://hyperpg.site/forward/35.163.52.26/8000",
        "address": "0xe0b9E3BF7463765eb55a3741feBdFEA3d50010Ab",
    },
    "AWSTillingService4": {
        "url": "https://hyperpg.site/forward/44.224.45.245/8000",
        "address": "0x612a58ec2483886e80859E56c595BA487F1aC349",
    },
    "AWSTillingService5": {
        "url": "https://hyperpg.site/forward/35.80.211.192/8000",
        "address": "0x1DE18E18d99f22b4280C16f4404e9933C2cbc377",
    },
    "AWSTillingService6": {
        "url": "https://hyperpg.site/forward/52.36.184.246/8000",
        "address": "0x77204F97Ae49De1464f08D9E07ae4359ACa636A6",
    },
}
