# Manager mode script - Freelancing node

## Overview

The **Hypercycle Manager Mode** is designed to enhance interaction and utilization within the **Hypercycle ecosystem**. It enables two key functionalities:

1. **License Delegation** - A license owner can delegate usage rights to a third party.
2. **Node Assignment** - A Hypercycle Node owner can allow another user to assign their license to the node.

This model fosters greater ecosystem activity by facilitating collaboration between hardware and license owners:

- If a user owns a **Hypercycle Node (hardware)** but lacks a license, they can obtain one from another party.

- If a user has a **License (or ANFE)** but lacks the hardware to run a node, they can assign it to someone else’s node.

- Additionally, license owners who prefer not to manage node assignments can delegate control to a trusted user.

## Purpose of This Script

This script simplifies the process of assigning a **License/ANFE** to a known **Hypercycle Node**, streamlining management for both node and license owners.

## Installation

### Setting Up the Virtual Environment

It is recommended to use a virtual environment to manage dependencies for this project. A virtual environment ensures isolation and avoids conflicts with global Python packages. You will need Python installed to create and run the environment.

You can use one of the following Python modules to create a virtual environment:

#### Using venv (comes with Python)

```bash
python -m venv .venv
```

#### Using virtualenv

```bash
python -m virtualenv .venv
```

Both commands create a virtual environment in a folder named `.venv`. While the folder can have a different name, `.venv` is a widely accepted convention.

### Activating the Virtual Environment

To activate the virtual environment:

```bash
source .venv/bin/activate
```

>**NOTE**: If you used a folder name other than .venv, adjust the path accordingly.

### Checking the Active Virtual Environment

To ensure you are using the correct virtual environment, run the following command:

```bash
which python
```

The output should point to this project’s virtual environment, for example:

```bash
/home/user/projects/manager-mode-script/.venv/bin/python
```

### Upgrading pip (Optional)

Upgrading pip before installing packages can prevent potential errors:

```bash
python -m pip install --upgrade pip
```

>**NOTE**: This will only upgrade pip within the virtual environment.

### Installing Dependencies

Once the virtual environment is activated, install the required dependencies from requirements.txt:

```bash
pip install -r requirements.txt
```

After completing these steps, the environment is ready to run the script

---

## Usage

This script facilitates the assignment of a **License/ANFE** to a **Hypercycle Node** in Manager Mode.

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--license-anfe` | **Yes** | License or ANFE to assign. |
| `--node-url` | **Yes** | Hypercycle Node's HTTP endpoint. |
| `--private-key` | **Yes** | `0x`-prefixed hex private key of the license owner or delegated account. |
| `--testnet` | No | Flag to indicate testnet usage (omit for mainnet). |

### Examples

#### 1. Assigning a License to a Mainnet Node

```sh
python script.py \
    --license-anfe 4649559795958260 \
    --node-url http://hypercycle-node.example:8080 \
    --private-key 0x1a2b3c...privatekey
```

#### 2. Assigning a License to a Testnet Node

```sh
python script.py \
    --license-anfe 1125968626330429 \
    --node-url http://testnet-node.example:8080 \
    --private-key 0x4d5e6f...privatekey \
    --testnet
```

### Notes

- Ensure the provided **private key** has permissions to manage the License/ANFE.

- The **node URL** must be accessible and correctly configured.

- Use `--testnet` only for testnet environments; omit for mainnet.
